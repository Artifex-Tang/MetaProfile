# 实现计划：enrich 真实补全 + ingest_ods UI 化

设计依据：`docs/superpowers/specs/2026-06-18-enrich-worker-ods-ui-design.md`
方法：TDD（先测试后实现）。每任务 implement → 测试 → commit。

---

## Phase 1 — B1 评分展示（最小、立即可见）

**T1** 4 画像 response schema 加 veracity_score/timeliness_score/data_as_of 字段
- 改 `metaprofile/profile_*/schemas/response.py` ×4（TechProfileResponse 等继承自 entity schema，确认基类是否已含；不含则加）
- 测试：`tests/unit/test_profile_response_scores.py` 断言 4 画像 response 序列化含 3 字段

**T2** `orm_to_response` ×4 带上 3 评分字段
- 改 `metaprofile/profile_*/services/*_profile_service.py` 的 orm_to_response
- 测试：构造 ORM 行（含评分）→ orm_to_response → 字段对齐

**T3** 前端 4 画像详情 Drawer「基本信息」加「数据质量」Card
- 改 `frontend/src/pages/Profile{Tech,Project,Org,Person}/index.tsx` ×4
- 加 3 指标展示（veracity/timeliness 进度条 + data_as_of 日期）
- vitest：Card 渲染 3 指标

---

## Phase 2 — A enrich 核心（后端，直写 typed ORM）

**T4** 抽 shared enrich 核心 `metaprofile/shared/enrich/orm_enricher.py`
- `async def enrich_one(session, orm_cls, id_col, entity_type, id, llm) -> EnrichResult`
- 流程：load ORM → completeness scorer 算缺失 → LLMGateway.complete() 填 → confidence≥阈值 setattr + 重算 completeness + data_as_of=now → EntityChangeLog(method=llm_enrich) → commit
- 复用 `foundation/enrichment/completeness.py` 的 _FIELD_SPEC + score
- 测试：mock LLM → 低 completeness ORM → 填字段 → ORM 更新 + completeness 上涨 + ChangeLog

**T5** 4 画像 `enrichment_worker.enrich_one` 真实现（调 shared 核心）
- 改 `metaprofile/profile_*/workers/enrichment_worker.py` ×4：enrich_one(id) 自开 session 调 shared 核心
- 测试：mock，断言调用链

**T6** `trigger()` 派发 celery + `get_task_status(task_id)`
- 改 `metaprofile/profile_*/services/*_enrichment_service.py` ×4
- trigger: completeness<0.6 → enrich_one.delay(...)；≥0.6 skipped
- get_task_status: celery AsyncResult(id).state + result
- 测试：mock celery delay + AsyncResult states

**T7** GET `/profile/{type}/enrich/task/{task_id}` 路由
- 改 `metaprofile/profile_*/api/routes_enrichment.py` ×4
- 测试：route 返 status

---

## Phase 3 — A celery worker 部署

**T8** 共享 celery_app `metaprofile/shared/worker/celery_app.py`
- broker=settings.rabbitmq.url, backend=settings.redis.dsn
- 4 画像 celery_app.py 改 import 共享（或保留 thin wrapper）
- 删/调整 beat_schedule 去掉悬空 full_rebuilder + 被否项
- 测试：import + app.task 注册

**T9** compose 加 backend-worker service
- `deploy/docker-compose.yml`：复用 backend 镜像，command `celery -A metaprofile.shared.worker.celery_app worker -l info`
- 验证：worker 起来注册 enrich_one 任务

---

## Phase 4 — A 前端 enrich 轮询

**T10** enrich 按钮轮询状态机
- 改 `frontend/src/api/{tech,org,person,project}.ts` ×4：加 getEnrichTaskStatus(taskId)
- 改 4 画像详情 enrich 按钮：POST→task_id → 轮询 GET → queued/running/success → 刷新详情
- vitest：状态机

---

## Phase 5 — B2 后端 db_connections CRUD + 任务统计

**T11** DbConnectionService + routes_db_connections
- `metaprofile/settings_api/services/db_connection_service.py`：list/create/update/delete，密码加密（复用 ingest_ods/services/security.py）、脱敏读
- `metaprofile/settings_api/api/routes_db_connections.py`：CRUD 路由
- 测试：CRUD 生命周期 + 密码不回显 + unique name

**T12** 任务运行统计接口
- 扩展 `settings_api` collection 路由：按 collection_task.id 聚合 ingest_raw(status) + ingest_errors count
- 测试：聚合正确

---

## Phase 6 — B2 前端 Settings

**T13** Settings「数据连接」tab
- 改 `frontend/src/pages/Settings/index.tsx`：新 tab，db_connections 表格 + 新增/编辑 Modal + 删除
- `frontend/src/api/settings.ts`：dbConnections CRUD

**T14** 采集任务 tab 运行历史展开
- collection_tasks 行展开：last_run_*、records_*、ingest_raw/ingest_errors 统计
- vitest

---

## Phase 7 — 集成 + 回归

**T15** e2e：enrich 端点返 task_id（worker 起则验补全）+ db_connections CRUD + 任务统计
**T16** 全套回归：`py -3.12 tests/e2e/api_tests.py` + `run_tests.py` + `cd frontend && npx vitest run`
**T17** regen 测试报告（#6 脚本）纳入新端点

---

## 关键约束
- 直写 typed ORM（不碰 entity_store）
- enrich confidence 阈值：≥0.8 自动写，0.6~0.8 审核（沿用 settings.thresholds）
- celery worker 仅跑 enrich_one（不碰 incremental/stats/full_rebuilder）
- 无新 migration
- 4 画像统一模式，抽 shared 核心 + ORM 适配，避免 4 份重复
