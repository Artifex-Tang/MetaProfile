# 非中文数据策略 + 通用定时任务调度器 设计

- 日期：2026-06-20
- 范围：① UI 显示兜底（name_cn 空→name_en→id）；② en→cn 翻译（单条/批量/cron 三触发）；③ **通用 cron 调度器**（DB 驱动 cron 表达式，激活翻译定时 + 顺带激活采集定时现死字段）
- 关联：弱信号 spec（附件 clean_content 第 4 语料源无关本 spec）；enrich worker（翻译复用其 LLMGateway + changeLog 模式）
- 后续：writing-plans 出实现计划

---

## 1. 背景与技术问题

### 1.1 业务背景
系统中文导向（UI/搜索/展示以中文为主）。但 ODS 真数据中大量实体源自**英文语料**（science 论文 title/abstract/keyword 全英、intl 机构/人员英文名）。现状：
- `tech_name_cn` 等 schema **已放宽**（`default=""`，非必填，commit f557e00），故英文源实体常 `name_cn=""` + `name_en="..."`。
- **搜索已双语**：4 画像 search 均 `name_cn.ilike OR name_en.ilike OR summary.ilike`（已实现，非缺口）。
- **UI 显示无兜底**：`name_cn=""` 时列表/详情/drawer/关系节点**显空白**（或回退 id），分析师看不到实体名。
- **无 en→cn 翻译能力**：英文源实体 name_cn 永久空白，靠人工补不现实。

### 1.2 技术问题
1. **显示缺口**：name_cn 空时无 name_en 兜底，UI 可见性差。
2. **翻译缺失**：需 LLM en→cn 自动补 name_cn，且要可控（单条/批量/定时），失败不破坏数据。
3. **定时基建缺失**：`schedule_cron` 字段（DataSourceConfigORM + Settings UI）**全项目无调度器消费**（无 APScheduler / 无 celery beat 读它 / 无 poller）；4 个 profile worker 的 `celery_app.beat_schedule` 是**静态占位**（`schedule: 86400.0 # 实际项目用 crontab`，未写真 cron），shared/worker/celery_app **无 beat**。→ 「任务配置里 CRON 定时执行」需新建调度器。建后翻译可 cron，**采集定时也顺带激活**（现 schedule_cron 采集也是死的）。

---

## 2. 总体架构

```
通用 cron 调度器(§3):
  shared/worker/celery_app 加静态 beat "scheduler_tick" 每60s
    → shared/scheduler/poller.py: 读 enabled scheduled_task(cron+last_run_at)
        croniter 判到期 → 按 task_type dispatch celery task → 更新 last_run_at/status
  task_type 注册表: {collection→trigger_collection_task, translate_batch→batch_translate_names}

翻译(§4):
  shared/enrich/translator.py: translate_name_one(db,type,id)
    name_cn空&name_en有 → LLMGateway en→cn → 写 name_cn + EntityChangeLog(llm_translate)
  shared/worker/translate_tasks.py:
    translate_name(type,id)        # 单条 celery(单条按钮)
    batch_translate_names(type?)   # 批量 celery(批量按钮 + cron)

触发(§5):
  单条: POST /profile/{type}/{id}/translate → translate_name.delay + 轮询
  批量: POST /settings/translate/batch → batch_translate_names.delay
  cron:  scheduled_task(task_type=translate_batch,cron,params) → poller dispatch

UI 兜底(§6):
  utils/displayName.ts: displayName(e)=name_cn||name_en||id; isUntranslated(e)
  4画像列表/详情/drawer/关系节点 → displayName + Tooltip + 单条翻译按钮
```

---

## 3. 通用 cron 调度器（基建，可复用）

### 3.1 数据模型
新表 `scheduled_task`（migration）：

| 列 | 类型 | 说明 |
|---|---|---|
| id | int PK | |
| name | str(128) | 任务名 |
| task_type | str(32) | 受控：`collection` / `translate_batch` |
| cron | str(64) | cron 表达式（5 段，如 `0 2 * * *`） |
| params | json | 任务参数（如 `{"entity_type":"tech"}` / `{"source_id":1}`） |
| enabled | bool | 是否启用 |
| last_run_at | datetime | 上次执行时间（poller 写） |
| last_status | str(32) | `ok/failed/running` |
| created_at/updated_at | datetime | |

**唯一约束**：(name)。cron 用 5 段标准表达式。

### 3.2 tick 入口（用已有 celery beat，不新建进程）
`shared/worker/celery_app.py` 加一条**静态** beat：
```python
celery_app.conf.beat_schedule = {
    "scheduler-tick": {"task": "metaprofile.scheduler.tick", "schedule": 60.0},
}
```
（60s 一次。cron 精度到分钟足够。）

### 3.3 poller
`shared/scheduler/poller.py`：
```python
async def _tick() -> dict:
    # 读 enabled scheduled_task，croniter 判 (cron, last_run_at) 是否该现在跑
    # 到期 → _dispatch(task_type, params) → 更新 last_run_at/last_status
    ...

@celery_app.task(name="metaprofile.scheduler.tick", bind=True)
def scheduler_tick(self):
    return asyncio.run(_tick())
```
- **到期判定**：`croniter(cron, last_run_at or 一足够早时间).get_next(datetime) <= now` → 到期。
- **幂等**：dispatch 前先写 `last_run_at=now, last_status=running`，避免 tick 重入重复发。
- **dispatch 注册表** `TASK_DISPATCH: dict[str, Callable]`：
  - `collection` → 调采集（按 params.source_id 触发 `trigger_collection` 等价路径）。
  - `translate_batch` → `batch_translate_names.delay(**params)`。

### 3.4 采集 cron 活化
现有 `DataSourceConfigORM.schedule_cron`（死字段）→ 提供一次性映射：DataSourceConfig 有 schedule_cron 且非空 → 视为 `scheduled_task(task_type=collection, cron=..., params={source_id})`。poller 统一消费 scheduled_task（不再单独读 DataSourceConfig.schedule_cron）。**迁移**：seed/启动时把现有 schedule_cron 同步成 scheduled_task 行（best-effort，去重 by name）。

---

## 4. 翻译核心

### 4.1 字段映射（per entity_type）
| type | name_cn 字段 | name_en 字段 |
|---|---|---|
| tech | `tech_name_cn` (str) | `tech_name_en` (str) |
| org | `name_cn` (str) | `name_en` (str) |
| person | `name_cn` (str) | `name_en` (str) |
| project | `name_cn` (list) | `name_en` (list) |

project 取/写 `[0]`。统一访问器：`_get_name(orm, type, lang)` / `_set_name_cn(orm, type, val)`。

### 4.2 translate_name_one
`shared/enrich/translator.py`：
```python
async def translate_name_one(db: AsyncSession, entity_type: str, entity_id: str) -> TranslateOutcome:
    # 1. 取 ORM（按 type→ORM 类 + id 列）
    # 2. name_cn 非空 → skip(no-op)
    # 3. name_en 空 → skip(no source)
    # 4. LLMGateway en→cn（术语翻译 prompt，禁意译/加注）
    # 5. 写 name_cn + EntityChangeLog(entity_id, method="llm_translate",
    #    field=name_cn, old=None, new=译值, reason="en→cn translate")
    # 6. 返回 TranslateOutcome(translated/skipped/failed, old, new, error)
```
- LLM 失败 → outcome.failed，**不写** name_cn（不污染）。
- project name_cn 是 list → 写 `[译值]`。

### 4.3 LLM prompt（en→cn 术语）
经 `LLMGateway`（复用 enrich 同款 glm 直连，commit 42d0118）。system: 「你是科技术语翻译器。把英文技术/机构/人名译为中文专业术语，只输出译文，禁音译加注、禁解释。」user: name_en。解析取首行。

---

## 5. celery 任务 + 端点

### 5.1 translate_tasks
`shared/worker/translate_tasks.py`（仿 `scan_tasks.py` 模板：`@celery_app.task(bind=True)` + `run_async(_async_xxx)`（**用 `shared/worker/async_runner.run_async`，非 `asyncio.run`**，避免 asyncpg 跨任务 'Event loop is closed'）+ `get_session()`）：
```python
@celery_app.task(name="metaprofile.translate.name", bind=True)
def translate_name(self, entity_type, entity_id): ...      # 单条

@celery_app.task(name="metaprofile.translate.batch", bind=True)
def batch_translate_names(self, entity_type=None): ...      # 批量分页扫 name_cn 空
```
- batch：分页（page_size 100）扫指定 type（None=全 4 type）`name_cn IS NULL OR name_cn=''` 且 name_en 非空 → 逐条 translate_name_one → 统计 translated/skipped/failed。
- 注册到 `shared/worker/celery_app.include`。

### 5.2 端点
- **单条**：4 画像**各自**加（与 enrich 同款 per-profile 模式，commit 4eae9f2）：`POST /api/v1/profile/{type}/{id}/translate` → 返 `{task_id}`；`GET /api/v1/profile/{type}/translate/task/{task_id}` 轮询状态。前端 4 画像 api 各加 `translate` + `getTranslateTaskStatus`（照搬 `enrich`/`getEnrichTaskStatus`）。
- **批量**：`POST /api/v1/settings/translate/batch?entity_type=tech` → 返 `{task_id}`（async，entity_type 缺省=全部 4 类）。

---

## 6. UI 兜底 + 审计

### 6.1 共享 helper
`frontend/src/utils/displayName.ts`：
```typescript
export function displayName(e: { name_cn?: string|null; name_en?: string|null; id: string }): string {
  return (e.name_cn && e.name_cn.trim()) || (e.name_en && e.name_en.trim()) || e.id
}
export function isUntranslated(e): boolean {
  return !((e.name_cn||'').trim()) && !!((e.name_en||'').trim())
}
```
（tech 用 `tech_name_cn/tech_name_en` → 调用方适配传参，或 helper 接受通用 `{cn,en,id}`。）

### 6.2 兜底组件
`frontend/src/components/EntityName.tsx`：显 `displayName`；`isUntranslated` → 包 `<Tooltip title={"原文: "+name_en+"（点翻译）"}>` + 末尾小 `<Button size="small" onClick={translate}>译</Button>`（点 → POST translate → 轮询 → 刷新）。复用于所有审计点。

### 6.3 审计点（全部替换空白 name_cn 显示）
1. 4 画像**列表列**（`ProfileTech/index.tsx:357` 等 tech_name_cn 列）→ render 用 EntityName。
2. 4 画像**详情 Descriptions 中文名字段**（`ProfileTech/index.tsx:152`）→ EntityName。
3. 4 画像 **drawer 标题**（`ProfileTech/index.tsx:120` `{p?.tech_name_cn ?? id}`）→ displayName。
4. `JumpBreadcrumb` selfName（null 时显 name_en）。
5. **关系网络节点名**（`routes_signals.py` `name_map[rid]=... or rid`）→ 后端 fallback name_en；前端 RelationGraph/PathGraph label 已 `?? id.slice(0,8)` → 改 displayName。
6. **弱信号 related 名**（同上路径）。
7. **编辑表单**（`ProfileTech/index.tsx:444` `tech_name_cn rules=[{required:true}]`）→ 放宽：name_en 有时 name_cn 可空（与 schema default="" 一致）。

---

## 7. 任务配置 UI（Settings）

- 通用 `scheduled_task` 管理：**列表**（name/task_type/cron/enabled/last_run_at/last_status/操作）+ **新建/编辑**表单（task_type 下拉[采集/翻译批量] + cron 输入 + params JSON + enabled）+ **立即执行**按钮（直接 dispatch，绕 poller，写 last_run_at）。
- 复用现 `schedule_cron` 表单范式（`Settings/index.tsx:404`）。
- cron 校验：前端 5 段格式提示；后端 `croniter.is_valid()` 校验（422）。
- 翻译批量作为首个 task_type 用户；采集 collection 由 §3.4 映射而来（也可在此 UI 管）。

---

## 8. 实施步骤（高层次，writing-plans 细化）

1. **调度器基建**：`scheduled_task` 表 + migration；`poller.py` + `scheduler_tick` beat；task_type dispatch 注册表；croniter 依赖。
2. **采集 cron 活化**：DataSourceConfig.schedule_cron → scheduled_task 映射（seed/启动同步）。
3. **翻译核心**：`translator.py` `translate_name_one` + 字段映射 + LLM prompt + changeLog。
4. **celery 任务**：`translate_tasks.py` 单/批 + 注册 include。
5. **端点**：单条 translate + 轮询；批量 translate。
6. **UI helper**：`displayName.ts` + `EntityName.tsx`。
7. **审计替换**：7 类显示点全换 + 编辑表单放宽。
8. **任务配置 UI**：scheduled_task CRUD + 立即执行 + cron 校验。
9. **测试**：poller 到期判定（croniter）+ translator（mock LLM）+ tasks + 端点 + EntityName/displayName 单测 + e2e（翻译按钮跑通 + cron 到期触发）。

---

## 9. 有益效果
- 英文源实体 UI 可见（name_en 兜底 + 翻译入口），分析师不再看到空白。
- LLM en→cn 自动补 name_cn，三触发（单/批/cron）覆盖全场景，失败不污染。
- **通用 cron 调度器**激活定时能力：翻译定时 + 采集定时（修复长期死字段 schedule_cron）。
- DB 驱动 cron，UI 可配，无需改代码调周期。

---

## 10. 非目标（YAGNI）
- 不做翻译回填**其他字段**（只 name_cn）。
- cron 不做依赖链/复杂重试/优先级（到期即发，失败记 last_status）。
- 不做 OCR / 附件（无关本 spec，附件见独立 spec）。
- 不做翻译质量评分/人工复核流（YAGNI，LLM 直写 + changeLog 可追溯）。
- 不统一 entity search 后端（已双语，复用现有 4 search）。
- celery beat 只加**一条** scheduler_tick（不每任务一条静态 beat；真 cron 由 DB 驱动）。

---

## 11. 关键文件清单

**新增**
- `metaprofile/shared/scheduler/poller.py`（scheduler_tick + croniter 到期 + dispatch）
- `metaprofile/shared/enrich/translator.py`（translate_name_one + 字段映射）
- `metaprofile/shared/worker/translate_tasks.py`（translate_name / batch_translate_names）
- `metaprofile/settings_api/domain/scheduled_task_orm.py`（ScheduledTaskORM）+ migration
- `metaprofile/settings_api/services/scheduler_service.py`（CRUD + dispatch + 立即执行）
- `frontend/src/utils/displayName.ts`、`frontend/src/components/EntityName.tsx`

**改**
- `metaprofile/shared/worker/celery_app.py`（beat_schedule 加 scheduler_tick；include 加 translate_tasks）
- 4 画像 routes（加 `/translate` + 轮询）
- `metaprofile/settings_api/api/*`（translate/batch + scheduled_task CRUD 路由）
- `metaprofile/new_tech_discovery/api/routes_signals.py`（节点名 fallback name_en）
- `frontend/src/pages/Profile*/index.tsx`（7 审计点 + 编辑表单放宽）
- `frontend/src/pages/Settings/index.tsx`（scheduled_task 管理 UI）

**依赖**：`croniter`（pip）。

**相关**：[[project-enrich-ods-ui-progress]] [[project-cross-profile-design]] [[project-ui-data-backlog]]
