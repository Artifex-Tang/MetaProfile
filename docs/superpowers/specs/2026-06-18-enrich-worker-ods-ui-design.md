# enrich 真实补全 + ingest_ods UI 化 设计文档

日期：2026-06-18 ｜ 状态：待评审 ｜ 对应待办 #4

---

## 1. 背景与问题

### 1.1 两套平行世界（诊断）

探查发现系统存在两套互不同步的画像数据路径：

| | World A（现役 / 交付） | World B（孤儿 / 桩） |
|---|---|---|
| 摄入路径 | `ingest_ods`（ODS→typed ORM+Neo4j） | `foundation/storage`（entity_store JSONB） |
| 存储 | typed ORM 表（`tech_profile` 等） | `entity_store` JSONB |
| profile API 读 | ✅ 是 | ❌ 否（grep 证实 `profile_*`/`backend` 零引用 entity_store） |
| 测试 | 414 passed，已合并 main | 仅 foundation 自测 |
| 状态 | 完整可用 | 全桩 |

### 1.2 World B 的 worker 桩与 ingest_ods 重复

4 画像各 4 个 celery worker 任务（全桩）：

| World B 桩 | 重复的 World A 能力 |
|---|---|
| `incremental_builder.run` | `ingest_ods/extractor`（建画像） |
| `enrichment_worker.scan_and_enrich`+pipeline | `ingest_ods/content_miner`+`scorer`（LLM 填+评分） |
| `stats_worker.compute_daily` | profile `*_stats_service`（live SQL 统计） |
| `full_rebuilder.run`（文件不存在，beat 悬空引用） | ingest_ods 全量重跑 |

**结论**：补全 World B 全部桩 = 用错存储重造 World A 已有能力 = 浪费。已与用户确认放弃。

### 1.3 唯一真实价值点

- **enrich 按钮**（`POST /profile/{type}/{id}/enrich`）：手册承诺的「LLM 补全」按钮，当前 `trigger()` 仅 log「queued」，零实际补全。
- **评分列隐形**：`veracity_score`/`timeliness_score`/`data_as_of` 已在 4 画像 ORM（migration 0003），但 profile response schema / UI **零引用**——ingest_ods scorer 算了没人看。
- **db_connections 无 UI**：ODS 连接配置仅 `seed_ods_datasources` 脚本写入，Settings 不暴露。
- **任务运行不可见**：`collection_tasks.last_run_*` + `ingest_raw`/`ingest_errors`/`relation_staging` 有数据但 UI 无运行历史/进度。

---

## 2. 范围（用户已确认）

### A. enrich 按钮 — 异步 celery worker（真活）
部署 1 个 celery worker 容器，**仅跑 `enrich_one`**（不碰被否的 incremental/stats/full_rebuilder 冗余桩）。trigger 派发 task，返 task_id，前端轮询状态。补全**直写 typed ORM**（UI 可见 + completeness 上涨）。

### B1. 评分展示
profile response schema + 详情页加「数据质量」区：`veracity_score`/`timeliness_score`/`data_as_of`。

### B2. ODS 连接配置 + 任务历史
- Settings 新增「数据连接」tab：`db_connections` CRUD（加密密码）。
- 采集任务 tab 增运行历史/进度（读 `collection_tasks.last_run_*` + `ingest_raw`/`ingest_errors` 统计）。

### 非目标
- ❌ 不补 incremental_builder / stats_worker / full_rebuilder（与 ingest_ods 重复）。
- ❌ 不桥接 entity_store → typed ORM（World B 保持现状，后续视情废弃）。
- ❌ 不动 foundation/enrichment pipeline（保留作 foundation 层参考，不接线）。
- ❌ 不新建数据模型/tab（见 §3.5）。

### 2.1 两个方向，统筹不合并

| | Direction 1: enrich（补） | Direction 2: ingest_ods（建） |
|---|---|---|
| 本质 | 已有画像填缺失字段 | 从数据源抽画像 |
| 方向 | profile → LLM → 补缺口 | source → 抽取 → 新画像 |
| 触发 | 画像详情「LLM补全」按钮（单条按需） | 数据源配置/采集任务（批量） |
| 输入 | 画像已有 attrs | ODS 表行 + 附件 |
| 输出 | patch 缺失字段，completeness 上涨 | 全新画像 + Neo4j 关系 |

**统筹点**：同写 typed ORM、同用 LLMProviderConfig、同写 EntityChangeLog、completeness 共享度量。
**天然衔接（不合并）**：ingest_ods 建稀疏画像（completeness 低）→ 详情页见评分+完整度不足 → 点「LLM补全」enrich 补 → completeness 上涨、data_as_of 刷新。流水线两段，合并必重现 World B 冗余。

---

## 3. 架构与决策

### 3.1 enrich 异步流

```
UI 点「LLM补全」
  → POST /profile/{type}/{id}/enrich
  → trigger(): 校验 completeness<0.6 → enrich_one.delay(type,id) → 返 {task_id, status:queued}
UI 持 task_id 轮询
  → GET /profile/{type}/enrich/task/{task_id}
  → celery AsyncResult(task_id).state + result → 返 {status, completeness_before/after, filled_fields}

celery worker (容器) 消费 enrich_one:
  1. SELECT typed ORM row by id
  2. completeness scorer 算缺失字段（复用 foundation/enrichment/completeness 的 _FIELD_SPEC）
  3. LLMGateway.complete() 填缺失字段（结构化 JSON，带 confidence）
  4. confidence ≥ 阈值 → setattr ORM + 重算 completeness + data_as_of=now
  5. EntityChangeLog 记录（method=llm_enrich）
  6. commit；返 EnrichmentResult
```

**worker 部署**：compose 加 1 个 service `backend-worker`，复用 backend 镜像，command = `celery -A metaprofile.profile_tech.workers.celery_app worker -l info`（按 profile_type 起 4 个或合并）。broker=RabbitMQ，backend=Redis（已配）。

### 3.2 celery_app 收敛
现状 4 画像各 1 份重复 `celery_app.py`（含被否的 beat_schedule）。收敛为**共享 celery app**（`metaprofile/shared/worker/celery_app.py`），4 画像 `enrich_one` 任务注册到同一 app，删除冗余 beat_schedule（或仅保留 enrich 相关，去掉 incremental/stats/full_rebuilder 悬空项）。

### 3.3 评分展示（B1）
- 后端：4 画像 response schema（`TechProfileResponse` 等）+ `orm_to_response` 加 3 字段。无新 migration（列已存在）。
- 前端：详情 Drawer「基本信息」tab 加「数据质量」Card（3 个指标，带进度条/标签）。

### 3.4 db_connections CRUD + 任务历史（B2）— UI 暴露，不新建模型
**数据模型已齐全**（探查证实）：`data_source_configs`(source_type=sql_warehouse, config_json 持 mode/db_connection_id/attachment_table/enable_relations) + `db_connections`(加密连接) + `collection_tasks`(status/records_*/log) 已完整建模 ingest_ods。ingest_ods 抽取**天然就是一条 collection_task**（`run_sql_warehouse_collection(task, source)` 已被 collector_service 调用）。

**缺的只是 UI 暴露**：
- 后端：`settings_api` 加 `routes_db_connections.py` + `DbConnectionService`（list/create/update/delete，密码加密写、脱敏不回显）+ 任务运行统计接口（按 collection_task 聚合 ingest_raw/ingest_errors）。
- 前端：Settings「数据连接」tab（db_connections CRUD 表格+Modal，**复用现有 Settings 框架**）；采集任务 tab 加运行历史展开（last_run_*、records_fetched/imported、ingest_raw 成功数、ingest_errors 数）。无新数据模型/tab 之外的结构。

### 3.5 不新建数据模型
无新 migration。所有功能基于现有表（db_connections / data_source_configs / collection_tasks / ingest_raw / ingest_errors / relation_staging / 4 画像含评分列）。仅在 response schema 层暴露已有列 + 补 UI。

---

## 4. 改动清单

### 后端
| 文件 | 改动 |
|---|---|
| `metaprofile/shared/worker/celery_app.py` | **新建** 共享 celery app（broker/backend 复用现有 settings） |
| `metaprofile/profile_*/workers/enrichment_worker.py` ×4 | `enrich_one` 真实现（直写 typed ORM + LLM + completeness + ChangeLog）；删 scan_and_enrich 桩或保留为 cron 调用 enrich_one 批量 |
| `metaprofile/profile_*/workers/celery_app.py` ×4 | 改 import 共享 app；beat_schedule 去掉悬空 full_rebuilder + 被否项 |
| `metaprofile/profile_*/services/*_enrichment_service.py` ×4 | `trigger()` 改 `enrich_one.delay()`；新增 `get_task_status(task_id)` 查 AsyncResult |
| `metaprofile/profile_*/api/routes_enrichment.py` ×4 | 新增 `GET .../enrich/task/{task_id}` |
| `metaprofile/profile_*/schemas/response.py` ×4 | 加 veracity/timeliness/data_as_of 字段 |
| `metaprofile/profile_*/services/*_profile_service.py` ×4 | `orm_to_response` 带上 3 评分字段 |
| `metaprofile/settings_api/api/routes_db_connections.py` | **新建** CRUD |
| `metaprofile/settings_api/services/db_connection_service.py` | **新建**（加密/脱敏） |
| `metaprofile/settings_api/api/routes_collection.py`（或扩展） | 新增任务运行统计接口（ingest_raw/errors 聚合） |
| `deploy/docker-compose.yml` | 加 `backend-worker` service |

### 前端
| 文件 | 改动 |
|---|---|
| `frontend/src/pages/Profile{Tech,Project,Org,Person}/index.tsx` ×4 | 详情 Drawer 加「数据质量」Card；enrich 按钮改轮询 task 状态 |
| `frontend/src/api/{tech,org,person,project}.ts` ×4 | enrich 返 task_id 后加 `getEnrichTaskStatus(taskId)` |
| `frontend/src/pages/Settings/index.tsx` | 新增「数据连接」tab + 采集任务展开历史 |
| `frontend/src/api/settings.ts`（或新 dbConnections.ts） | dbConnections CRUD + 任务统计接口 |

---

## 5. 数据模型

无新 migration 需求：
- `db_connections` 表已存在（migration 0003）。
- veracity/timeliness/data_as_of 列已存在（migration 0003）。
- collection_tasks/ingest_raw/ingest_errors/relation_staging 已存在。

仅在 response schema 层暴露已有列。

---

## 6. 测试计划（TDD）

### 后端 pytest
- `enrich_one` 单测：mock LLMGateway → 给定低 completeness ORM 行 → 填字段 → 断言 ORM 更新 + completeness 上涨 + ChangeLog 写入。
- `trigger` 单测：completeness<0.6 → 调 delay（mock celery）→ 返 queued；≥0.6 → skipped。
- `get_task_status` 单测：mock AsyncResult states (PENDING/SUCCESS/FAILURE)。
- 评分展示：profile response 含 3 字段。
- db_connections CRUD：加密写、脱敏读、unique name 冲突。
- 任务统计：ingest_raw/errors 聚合正确。
- enrich route：POST 返 task_id；GET task 状态。

### 前端 vitest
- 数据质量 Card 渲染 3 指标。
- enrich 按钮轮询状态机（queued→running→success/failed）。

### e2e（tests/e2e）
- API：enrich 端点返 task_id（若 worker 起则验补全，否则验结构）。
- db_connections CRUD 生命周期。
- 任务统计接口。

---

## 7. 风险与取舍

| 风险 | 缓解 |
|---|---|
| celery worker 容器增加部署复杂度 | 复用 backend 镜像，单 service；compose opt-in 可关 |
| LLM 填字段 confidence 不可控致脏数据 | 沿用 enrich 阈值（≥0.8 自动/0.6 审核）；低置信丢弃 + ChangeLog 标记 |
| 轮询 task 状态增加前后端耦合 | 复用 celery Redis backend AsyncResult，无新存储 |
| enrich 直写 ORM 绕过 foundation pipeline | 已与用户确认（foundation pipeline 目标 entity_store 与 UI 不符，不接线） |

---

## 8. 待写计划时定

- celery worker 单容器跑 4 profile_type 任务 vs 4 容器（倾向单容器多 task）。
- `scan_and_enrich` 批量定时补全：保留为 cron 调 enrich_one 批量，还是删？（倾向保留为批量入口，beat 改调 enrich_one）。
- enrich_one 跨 profile_type 统一实现 vs 4 份（倾向抽 shared 基类 + 4 ORM 适配）。
- db_connections 密码加密算法（复用 ingest_ods/services/security.py 现有加解密）。

---

相关：[[project_ods_extraction_design]] [[project_data_write_path]] [[project_test_deploy_state]]
