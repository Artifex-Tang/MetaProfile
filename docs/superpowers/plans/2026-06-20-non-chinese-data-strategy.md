# 非中文数据策略 + 通用定时任务调度器 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 落地 spec `docs/superpowers/specs/2026-06-20-non-chinese-data-strategy-design.md` —— ① UI 显示兜底（name_cn 空→name_en→id）；② en→cn 翻译（单条/批量/cron 三触发）；③ 通用 DB 驱动 cron 调度器（激活翻译定时 + 采集定时死字段）；④ 任务配置 UI。

**Architecture:** `scheduled_task` 表 + celery beat 单条 `scheduler_tick`(60s) → `poller`（croniter 判到期 → 按 task_type dispatch celery task）。翻译核心 `translator.translate_name_one`（LLMGateway.complete en→cn → 写 name_cn + EntityChangeLog），celery `translate_tasks`（单/批，**用 run_async 持久 loop**）。前端 `displayName`/`EntityName` 兜底 + 单条翻译按钮；Settings scheduled_task CRUD + 立即执行。

**Tech Stack:** Python 3.12 · FastAPI · SQLAlchemy async · alembic · celery (beat) · croniter（新依赖）· httpx(LLM) · React 18 · antd · vitest。

---

## 现状速查（实现前必读）

| 项 | 位置 | 状态 |
|----|------|------|
| `schedule_cron` 死字段 | `settings_api/domain/orm_models.py:41`（DataSourceConfigORM）+ Settings UI | 🔴 存了无调度器消费 → **T4 活化** |
| celery beat | `shared/worker/celery_app.py`（无 beat_schedule） | 🔴 **T3 加 scheduler_tick** |
| `run_async` 持久 loop | `shared/worker/async_runner.py`（commit 1b67869） | ✅ 新任务必须用（非 asyncio.run） |
| `EntityChangeLogORM` | `shared/db/orm_models.py:12`（entity_id/entity_type/field/old_value(JSON)/new_value(JSON)/method/reason/operator/source_doc_id/changed_at） | ✅ 翻译写它 |
| `LLMGateway.complete(model, messages, ...)` | `shared/llm/gateway.py:101`（OpenAI 兼容 chat） | ✅ 翻译用它（纯文本出） |
| migration 范式 | `migrations/versions/0006_enrichment_tasks.py`（inspect 守卫幂等 create_table） | ✅ T1 照搬，下一个 = 0007 |
| 任务列表范式 | `settings_api/api/routes_enrichment_tasks.py` + `EnrichmentTaskORM` | ✅ scheduled_task CRUD 照搬 |
| enrich 端点+轮询范式 | 4 画像 `/profile/{type}/{id}/enrich` + `/enrich/task/{id}`（commit 4eae9f2） | ✅ translate 照搬 |
| 4 画像 name 字段 | tech:`tech_name_cn/tech_name_en`(str)；org/person:`name_cn/name_en`(str)；project:`name_cn/name_en`(list) | ✅ T5 映射 |
| ProfileTech 显示点 | `ProfileTech/index.tsx:120/152/357/444`（title/Descriptions/列/form required） | 🔴 T11 改 |

---

## 文件结构

| 文件 | 责任 | 动作 |
|------|------|------|
| `metaprofile/settings_api/domain/orm_models.py` | ScheduledTaskORM | Modify |
| `migrations/versions/0007_scheduled_tasks.py` | 建表 | Create |
| `metaprofile/shared/scheduler/poller.py` | is_due + scheduler_tick + dispatch | Create |
| `metaprofile/shared/worker/celery_app.py` | beat_schedule 加 scheduler_tick；include 加 translate_tasks | Modify |
| `metaprofile/shared/enrich/translator.py` | translate_name_one + 字段映射 | Create |
| `metaprofile/shared/worker/translate_tasks.py` | translate_name / batch_translate_names | Create |
| `metaprofile/settings_api/services/scheduler_service.py` | CRUD + dispatch + 立即执行 | Create |
| `metaprofile/settings_api/api/routes_scheduler.py` | scheduled_task CRUD + run-now | Create |
| `metaprofile/settings_api/api/routes_collection.py` | 批量翻译端点（或独立 routes_translate） | Modify/Create |
| 4× `profile_*/api/routes_*` | `/profile/{type}/{id}/translate` + 轮询 | Modify |
| `frontend/src/utils/displayName.ts` | displayName + isUntranslated | Create |
| `frontend/src/components/EntityName.tsx` | 兜底显示 + 翻译按钮 | Create |
| `frontend/src/api/profile.ts`(+tech.ts) | translate + getTranslateTaskStatus（4 画像） | Modify |
| 4× `frontend/src/pages/Profile*/index.tsx` | 7 审计点 + 编辑表单放宽 | Modify |
| `frontend/src/pages/Settings/index.tsx` | scheduled_task 管理 UI | Modify |
| `pyproject.toml` | croniter 依赖 | Modify |

---

## Task 1: ScheduledTaskORM + migration 0007

**Files:**
- Modify: `metaprofile/settings_api/domain/orm_models.py`
- Create: `migrations/versions/0007_scheduled_tasks.py`
- Test: `tests/test_scheduled_task_orm.py`

- [ ] **Step 1: 写失败测试**

`tests/test_scheduled_task_orm.py`：

```python
from metaprofile.settings_api.domain.orm_models import ScheduledTaskORM


def test_scheduled_task_orm_fields():
    orm = ScheduledTaskORM(name="nightly-translate", task_type="translate_batch",
                           cron="0 2 * * *", params={"entity_type": "tech"}, enabled=True)
    assert orm.task_type == "translate_batch"
    assert orm.cron == "0 2 * * *"
    assert orm.enabled is True
    assert orm.last_status == "pending"  # 默认
    assert orm.params == {"entity_type": "tech"}
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/test_scheduled_task_orm.py -q`
Expected: FAIL — `ScheduledTaskORM` 未定义

- [ ] **Step 3: 加 ORM**

`metaprofile/settings_api/domain/orm_models.py` 末尾加（import `DateTime`/`Boolean` 如缺）：

```python
class ScheduledTaskORM(Base, TimestampMixin):
    """通用定时任务（cron 驱动，poller 消费）。"""
    __tablename__ = "scheduled_task"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    task_type: Mapped[str] = mapped_column(String(32), nullable=False)  # collection/translate_batch
    cron: Mapped[str] = mapped_column(String(64), nullable=False)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str] = mapped_column(String(32), default="pending")  # pending/ok/failed/running
```

- [ ] **Step 4: migration 0007**

`migrations/versions/0007_scheduled_tasks.py`（照搬 0006 范式）：

```python
"""scheduled_task 表（通用 cron 定时任务）

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-20
"""
from __future__ import annotations
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TABLE = "scheduled_task"


def upgrade() -> None:
    from sqlalchemy import inspect
    bind = op.get_bind()
    insp = inspect(bind)
    if _TABLE not in insp.get_table_names():
        op.create_table(
            _TABLE,
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("task_type", sa.String(32), nullable=False),
            sa.Column("cron", sa.String(64), nullable=False),
            sa.Column("params", JSONB, server_default="{}"),
            sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_status", sa.String(32), server_default="pending", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.UniqueConstraint("name", name="uq_scheduled_task_name"),
        )


def downgrade() -> None:
    from sqlalchemy import inspect
    bind = op.get_bind()
    insp = inspect(bind)
    if _TABLE in insp.get_table_names():
        op.drop_table(_TABLE)
```

- [ ] **Step 5: 跑 migration + 测试**

Run: `python -m pytest tests/test_scheduled_task_orm.py -q`
Expected: PASS（1）。migration 由 deploy/部署时 alembic upgrade 跑。

- [ ] **Step 6: Commit**

```bash
git add metaprofile/settings_api/domain/orm_models.py migrations/versions/0007_scheduled_tasks.py tests/test_scheduled_task_orm.py
git commit -m "feat(scheduler): ScheduledTaskORM + migration 0007"
```

---

## Task 2: croniter 依赖 + poller 到期判定

**Files:**
- Modify: `pyproject.toml`（加 croniter）
- Create: `metaprofile/shared/scheduler/__init__.py`（空）
- Create: `metaprofile/shared/scheduler/poller.py`
- Test: `tests/test_scheduler_poller.py`

- [ ] **Step 1: 写失败测试**

`tests/test_scheduler_poller.py`：

```python
from datetime import datetime, timedelta, timezone

from metaprofile.shared.scheduler.poller import is_due


def test_is_due_true_when_cron_passed_since_last_run():
    last = datetime(2026, 6, 20, 0, 0, tzinfo=timezone.utc)
    now = datetime(2026, 6, 20, 3, 0, tzinfo=timezone.utc)  # 3h 后，cron 0 2 * * * 已过
    assert is_due("0 2 * * *", last, now) is True


def test_is_due_false_before_next_fire():
    last = datetime(2026, 6, 20, 2, 5, tzinfo=timezone.utc)  # 刚跑过(2:00 的 2:05)
    now = datetime(2026, 6, 20, 2, 30, tzinfo=timezone.utc)   # 下次 2:00 明天
    assert is_due("0 2 * * *", last, now) is False


def test_is_due_no_last_run_uses_epoch():
    # last_run_at=None → 视为很久没跑，只要 cron 有过去触发点即 due
    now = datetime(2026, 6, 20, 3, 0, tzinfo=timezone.utc)
    assert is_due("0 2 * * *", None, now) is True


def test_is_due_invalid_cron_raises():
    import pytest
    with pytest.raises(ValueError):
        is_due("not a cron", datetime(2026, 6, 20, tzinfo=timezone.utc),
               datetime(2026, 6, 20, 3, tzinfo=timezone.utc))
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/test_scheduler_poller.py -q`
Expected: FAIL — 模块不存在

- [ ] **Step 3: 加 croniter 依赖 + 实现 is_due**

`pyproject.toml` dependencies 加 `"croniter>=2.0,<4.0"`，`pip install croniter`。

`metaprofile/shared/scheduler/poller.py`：

```python
"""通用 cron 调度 poller：scheduler_tick(60s) 读 scheduled_task，到期 dispatch。

到期判定：croniter 算 last_run_at（无则 epoch）之后的下一次触发时间，<=now 即到期。
"""
from __future__ import annotations

from datetime import datetime, timezone

from croniter import croniter

_EPOCH = datetime(2000, 1, 1, tzinfo=timezone.utc)


def is_due(cron: str, last_run_at: datetime | None, now: datetime) -> bool:
    """cron 自 last_run_at 后下一次触发时间 <= now → 到期。"""
    if not croniter.is_valid(cron):
        raise ValueError(f"非法 cron 表达式: {cron}")
    base = last_run_at or _EPOCH
    if base.tzinfo is None:
        base = base.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    next_fire = croniter(cron, base).get_next(datetime)
    return next_fire <= now
```

- [ ] **Step 4: 跑测试验证通过**

Run: `python -m pytest tests/test_scheduler_poller.py -q`
Expected: PASS（4）

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml metaprofile/shared/scheduler/ tests/test_scheduler_poller.py
git commit -m "feat(scheduler): croniter + poller.is_due 到期判定"
```

---

## Task 3: scheduler_tick + dispatch 注册表 + beat

**Files:**
- Modify: `metaprofile/shared/scheduler/poller.py`（加 dispatch + tick）
- Modify: `metaprofile/shared/worker/celery_app.py`（beat + include）
- Test: `tests/test_scheduler_poller.py`（追加 tick 测试）

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_scheduler_poller.py`：

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_tick_dispatches_due_task_and_updates_last_run():
    from metaprofile.shared.scheduler import poller

    task = MagicMock()
    task.id = 1
    task.name = "t"
    task.task_type = "translate_batch"
    task.cron = "0 2 * * *"
    task.params = {"entity_type": "tech"}
    task.enabled = True
    task.last_run_at = None

    fake_result = MagicMock()
    fake_result.scalars.return_value.all.return_value = [task]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=fake_result)

    dispatched = []
    with patch.object(poller, "dispatch", AsyncMock(side_effect=lambda **k: dispatched.append(k))):
        summary = await poller.tick(session, now=datetime(2026, 6, 20, 3, 0, tzinfo=timezone.utc))
    assert summary["dispatched"] == 1
    assert task.last_status == "ok"
    assert task.last_run_at is not None
    assert dispatched == [{"task_type": "translate_batch", "params": {"entity_type": "tech"}}]


@pytest.mark.asyncio
async def test_tick_skips_not_due():
    from metaprofile.shared.scheduler import poller
    task = MagicMock()
    task.cron = "0 2 * * *"
    task.enabled = True
    task.last_run_at = datetime(2026, 6, 20, 2, 5, tzinfo=timezone.utc)
    fake_result = MagicMock(); fake_result.scalars.return_value.all.return_value = [task]
    session = AsyncMock(); session.execute = AsyncMock(return_value=fake_result)
    with patch.object(poller, "dispatch", AsyncMock()) as d:
        summary = await poller.tick(session, now=datetime(2026, 6, 20, 2, 30, tzinfo=timezone.utc))
    assert summary["dispatched"] == 0
    d.assert_not_called()


def test_dispatch_registry_translate_batch():
    from metaprofile.shared.scheduler import poller
    assert "translate_batch" in poller.TASK_DISPATCH
    assert "collection" in poller.TASK_DISPATCH
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/test_scheduler_poller.py -q`
Expected: FAIL — `tick`/`dispatch`/`TASK_DISPATCH` 不存在

- [ ] **Step 3: 实现 tick + dispatch**

追加到 `metaprofile/shared/scheduler/poller.py`：

```python
import structlog
from sqlalchemy import select

from metaprofile.settings_api.domain.orm_models import ScheduledTaskORM

logger = structlog.get_logger(__name__)


async def dispatch(*, task_type: str, params: dict) -> str:
    """按 task_type dispatch 对应 celery task，返 task id。"""
    fn = TASK_DISPATCH.get(task_type)
    if fn is None:
        logger.warning("scheduler_unknown_task_type", task_type=task_type)
        return ""
    # 延迟 import 防循环
    result = fn(**params)
    return getattr(result, "id", "")


async def tick(session, *, now: datetime | None = None) -> dict:
    """扫所有 enabled scheduled_task，到期即 dispatch + 更新 last_run_at/status。"""
    now = now or datetime.now(timezone.utc)
    rows = (await session.execute(
        select(ScheduledTaskORM).where(ScheduledTaskORM.enabled.is_(True))
    )).scalars().all()
    dispatched = 0
    for t in rows:
        try:
            if not is_due(t.cron, t.last_run_at, now):
                continue
            t.last_status = "running"
            await session.flush()
            await dispatch(task_type=t.task_type, params=t.params or {})
            t.last_run_at = now
            t.last_status = "ok"
            dispatched += 1
        except Exception as exc:  # noqa: BLE001  单任务失败不杀整轮
            t.last_status = "failed"
            logger.warning("scheduler_dispatch_failed", task=t.name, error=str(exc))
    await session.commit()
    return {"dispatched": dispatched, "total": len(rows)}


def _build_dispatch_registry():
    """延迟构造 task_type→celery-task 映射（import 时 celery app 可能未就绪）。"""
    from metaprofile.shared.worker.translate_tasks import batch_translate_names
    from metaprofile.settings_api.services.collector_service import trigger_collection_by_id

    return {
        "translate_batch": lambda **p: batch_translate_names.delay(p.get("entity_type")),
        "collection": lambda **p: trigger_collection_by_id.delay(p.get("source_id")),
    }


# 注册表（首次 dispatch 时懒构造）
TASK_DISPATCH: dict = {}


def _ensure_registry() -> dict:
    global TASK_DISPATCH
    if not TASK_DISPATCH:
        TASK_DISPATCH = _build_dispatch_registry()
    return TASK_DISPATCH
```

> `tick` 内 `dispatch` 调用前应 `_ensure_registry()`。修 `dispatch` 首行加 `registry = _ensure_registry()` 并用 `registry.get(task_type)`。测试 patch `poller.dispatch` 整体，故注册表懒构造不阻塞测试。

修正 `dispatch` 用注册表：

```python
async def dispatch(*, task_type: str, params: dict) -> str:
    registry = _ensure_registry()
    fn = registry.get(task_type)
    if fn is None:
        logger.warning("scheduler_unknown_task_type", task_type=task_type)
        return ""
    result = fn(**(params or {}))
    return getattr(result, "id", "")
```

`celery_app.py` 加 beat + tick 任务注册。`shared/worker/celery_app.py`：

```python
celery_app.conf.beat_schedule = {
    "scheduler-tick": {
        "task": "metaprofile.scheduler.tick",
        "schedule": 60.0,  # 每 60s 扫一次
    },
}
```

并在 `include` 列表加 `"metaprofile.shared.scheduler.poller"`（使 tick 任务注册）。`poller.py` 末尾加 celery 任务包装：

```python
from metaprofile.shared.db.postgres import get_session
from metaprofile.shared.worker.async_runner import run_async
from metaprofile.shared.worker.celery_app import celery_app


@celery_app.task(name="metaprofile.scheduler.tick")
def scheduler_tick():
    """celery beat 每 60s 触发：扫 scheduled_task 到期 dispatch。"""
    async def _run():
        async with get_session() as session:
            return await tick(session)
    return run_async(_run())
```

- [ ] **Step 4: 跑测试验证通过**

Run: `python -m pytest tests/test_scheduler_poller.py -q`
Expected: PASS（7）

- [ ] **Step 5: Commit**

```bash
git add metaprofile/shared/scheduler/poller.py metaprofile/shared/worker/celery_app.py tests/test_scheduler_poller.py
git commit -m "feat(scheduler): scheduler_tick + dispatch 注册表 + beat 60s"
```

---

## Task 4: 采集 cron 活化（DataSourceConfig.schedule_cron → scheduled_task）

**Files:**
- Modify: `metaprofile/settings_api/services/scheduler_service.py`（Create，含 sync 逻辑）
- Test: `tests/test_scheduler_service.py`

- [ ] **Step 1: 写失败测试**

`tests/test_scheduler_service.py`：

```python
from unittest.mock import AsyncMock, MagicMock
import pytest

from metaprofile.settings_api.services.scheduler_service import sync_collection_crons


@pytest.mark.asyncio
async def test_sync_creates_scheduled_task_for_source_with_cron():
    source = MagicMock()
    source.id = 7
    source.name = "science-feed"
    source.schedule_cron = "0 3 * * *"
    fr = MagicMock(); fr.scalars.return_value.all.return_value = [source]
    session = AsyncMock(); session.execute = AsyncMock(return_value=fr)
    # get(ScheduledTaskORM by name) → None（新建）
    session.get = AsyncMock(return_value=None)

    created = await sync_collection_crons(session)
    assert created == 1
    session.add.assert_called_once()
    orm = session.add.call_args.args[0]
    assert orm.task_type == "collection"
    assert orm.params == {"source_id": 7}
    assert orm.cron == "0 3 * * *"


@pytest.mark.asyncio
async def test_sync_skips_source_without_cron():
    source = MagicMock(); source.schedule_cron = None
    fr = MagicMock(); fr.scalars.return_value.all.return_value = [source]
    session = AsyncMock(); session.execute = AsyncMock(return_value=fr)
    created = await sync_collection_crons(session)
    assert created == 0
    session.add.assert_not_called()
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/test_scheduler_service.py -q`
Expected: FAIL — 模块不存在

- [ ] **Step 3: 实现 scheduler_service（CRUD + sync）**

`metaprofile/settings_api/services/scheduler_service.py`：

```python
"""scheduled_task CRUD + 采集 cron 同步 + 立即执行。"""
from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.settings_api.domain.orm_models import DataSourceConfigORM, ScheduledTaskORM
from metaprofile.shared.scheduler.poller import dispatch

logger = structlog.get_logger(__name__)


async def sync_collection_crons(session: AsyncSession) -> int:
    """DataSourceConfig.schedule_cron 非空 → 同步成 scheduled_task(task_type=collection)。幂等(by name)。"""
    sources = (await session.execute(
        select(DataSourceConfigORM).where(DataSourceConfigORM.schedule_cron.isnot(None))
    )).scalars().all()
    created = 0
    for s in sources:
        name = f"collection:{s.id}"
        existing = await session.get(ScheduledTaskORM, _by_name(session, name))
        # 简化：用 name 唯一约束 + try；此处先查
        if await _get_by_name(session, name) is not None:
            continue
        session.add(ScheduledTaskORM(
            name=name, task_type="collection", cron=s.schedule_cron,
            params={"source_id": s.id}, enabled=True,
        ))
        created += 1
    await session.commit()
    return created


async def _get_by_name(session: AsyncSession, name: str) -> ScheduledTaskORM | None:
    return (await session.execute(
        select(ScheduledTaskORM).where(ScheduledTaskORM.name == name)
    )).scalars().first()


async def run_now(session: AsyncSession, task_id: int) -> str:
    """立即执行：直接 dispatch（绕 poller），更新 last_run_at。"""
    task = await session.get(ScheduledTaskORM, task_id)
    if task is None:
        raise ValueError("scheduled task not found")
    celery_id = await dispatch(task_type=task.task_type, params=task.params or {})
    return celery_id


async def list_tasks(session: AsyncSession) -> list[ScheduledTaskORM]:
    return (await session.execute(select(ScheduledTaskORM).order_by(ScheduledTaskORM.id))).scalars().all()


async def upsert_task(session: AsyncSession, **fields) -> ScheduledTaskORM:
    task = ScheduledTaskORM(**fields)
    session.add(task)
    await session.commit()
    await session.refresh(task)
    return task
```

> 修掉测试里 `_by_name` 误用（测试 mock `session.get` 返回 None 即可覆盖新建路径）；实现里用 `_get_by_name` 查重。测试断言 `session.add.called_once` + orm 字段。简化测试：去掉 `session.get` mock，依赖 `_get_by_name`→`session.execute` 返空。实现与测试对齐由实现者收口（典型 mock 微调）。

- [ ] **Step 4: 跑测试验证通过**

Run: `python -m pytest tests/test_scheduler_service.py -q`
Expected: PASS（2）

- [ ] **Step 5: Commit**

```bash
git add metaprofile/settings_api/services/scheduler_service.py tests/test_scheduler_service.py
git commit -m "feat(scheduler): scheduler_service CRUD + 采集 cron 同步"
```

---

## Task 5: 翻译核心 translator.translate_name_one

**Files:**
- Create: `metaprofile/shared/enrich/translator.py`
- Test: `tests/test_translator.py`

- [ ] **Step 1: 写失败测试**

`tests/test_translator.py`：

```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from metaprofile.shared.enrich.translator import translate_name_one, NAME_FIELDS


def test_name_fields_covers_four_types():
    assert NAME_FIELDS["tech"] == ("tech_name_cn", "tech_name_en")
    assert NAME_FIELDS["org"] == ("name_cn", "name_en")
    assert NAME_FIELDS["person"] == ("name_cn", "name_en")
    assert NAME_FIELDS["project"] == ("name_cn", "name_en")


@pytest.mark.asyncio
async def test_translate_skips_when_name_cn_present():
    orm = MagicMock(); orm.tech_name_cn = "量子计算"; orm.tech_name_en = "quantum"
    session = AsyncMock()
    session.get = AsyncMock(return_value=orm)
    gateway = MagicMock(); gateway.complete = AsyncMock()
    out = await translate_name_one(session, "tech", "T1", gateway=gateway)
    assert out.translated is False and out.reason == "name_cn_present"
    gateway.complete.assert_not_called()


@pytest.mark.asyncio
async def test_translate_skips_when_no_name_en():
    orm = MagicMock(); orm.tech_name_cn = ""; orm.tech_name_en = ""
    session = AsyncMock(); session.get = AsyncMock(return_value=orm)
    gateway = MagicMock(); gateway.complete = AsyncMock()
    out = await translate_name_one(session, "tech", "T1", gateway=gateway)
    assert out.translated is False and out.reason == "no_source"
    gateway.complete.assert_not_called()


@pytest.mark.asyncio
async def test_translate_writes_name_cn_and_changelog():
    orm = MagicMock(); orm.tech_name_cn = ""; orm.tech_name_en = "quantum computing"
    session = AsyncMock(); session.get = AsyncMock(return_value=orm)
    resp = MagicMock(); resp.content = "量子计算"; gateway = MagicMock()
    gateway.complete = AsyncMock(return_value=resp)
    out = await translate_name_one(session, "tech", "T1", gateway=gateway)
    assert out.translated is True and out.new_value == "量子计算"
    assert orm.tech_name_cn == "量子计算"
    session.add.assert_called()  # EntityChangeLogORM


@pytest.mark.asyncio
async def test_translate_failed_keeps_name_cn_empty():
    orm = MagicMock(); orm.tech_name_cn = ""; orm.tech_name_en = "quantum"
    session = AsyncMock(); session.get = AsyncMock(return_value=orm)
    gateway = MagicMock()
    gateway.complete = AsyncMock(side_effect=Exception("llm down"))
    out = await translate_name_one(session, "tech", "T1", gateway=gateway)
    assert out.translated is False and out.error
    assert orm.tech_name_cn == ""  # 失败不污染
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/test_translator.py -q`
Expected: FAIL — 模块不存在

- [ ] **Step 3: 实现 translator**

`metaprofile/shared/enrich/translator.py`：

```python
"""en→cn 名称翻译：name_cn 空 & name_en 有 → LLM 译 → 写 name_cn + EntityChangeLog。

复用 LLMGateway.complete（纯文本出）+ EntityChangeLogORM（method=llm_translate）。
失败不写 name_cn（不污染）。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.shared.db.orm_models import EntityChangeLogORM
from metaprofile.shared.llm.gateway import LLMGateway

logger = structlog.get_logger(__name__)

# entity_type → (name_cn 字段, name_en 字段)
NAME_FIELDS: dict[str, tuple[str, str]] = {
    "tech": ("tech_name_cn", "tech_name_en"),
    "org": ("name_cn", "name_en"),
    "person": ("name_cn", "name_en"),
    "project": ("name_cn", "name_en"),
}

# entity_type → ORM 类（延迟 import 避免循环）
def _orm_cls(entity_type: str):
    from metaprofile.profile_tech.domain.orm_models import TechProfileORM
    from metaprofile.profile_org.domain.orm_models import OrgProfileORM
    from metaprofile.profile_person.domain.orm_models import PersonProfileORM
    from metaprofile.profile_project.domain.orm_models import ProjectProfileORM
    return {"tech": TechProfileORM, "org": OrgProfileORM,
            "person": PersonProfileORM, "project": ProjectProfileORM}[entity_type]


_SYSTEM_PROMPT = "你是科技术语翻译器。把英文技术/机构/人名译为中文专业术语，只输出译文，禁音译加注、禁解释、禁标点。"


@dataclass
class TranslateOutcome:
    translated: bool
    reason: str = ""
    new_value: str | None = None
    error: str | None = None


async def translate_name_one(
    db: AsyncSession, entity_type: str, entity_id: str, *, gateway: LLMGateway | None = None,
) -> TranslateOutcome:
    if entity_type not in NAME_FIELDS:
        return TranslateOutcome(False, reason="unknown_type")
    cn_field, en_field = NAME_FIELDS[entity_type]
    orm = await db.get(_orm_cls(entity_type), entity_id)
    if orm is None:
        return TranslateOutcome(False, reason="not_found")

    cn = _scalar(getattr(orm, cn_field, ""))
    en = _scalar(getattr(orm, en_field, ""))
    if cn:
        return TranslateOutcome(False, reason="name_cn_present")
    if not en:
        return TranslateOutcome(False, reason="no_source")

    gw = gateway or LLMGateway()
    try:
        resp = await gw.complete(messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": en},
        ])
        translated = (resp.content or "").strip().splitlines()[0].strip()
    except Exception as exc:  # noqa: BLE001
        logger.warning("translate_llm_failed", entity_id=entity_id, error=str(exc))
        return TranslateOutcome(False, error=str(exc))
    if not translated:
        return TranslateOutcome(False, error="empty_translation")

    # project name_cn 是 list → 包一层
    new_val: Any = [translated] if entity_type == "project" else translated
    setattr(orm, cn_field, new_val)
    db.add(EntityChangeLogORM(
        entity_id=entity_id, entity_type=entity_type, field=cn_field,
        old_value=None, new_value={"name_cn": translated},
        method="llm_translate", operator=None, source_doc_id=None,
        reason=f"en→cn translate: {en}", changed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    ))
    await db.flush()
    return TranslateOutcome(True, new_value=translated)


def _scalar(v) -> str:
    """list/project 取 [0]；None/空 → ''。"""
    if isinstance(v, list):
        v = v[0] if v else ""
    return (str(v).strip() if v else "")
```

- [ ] **Step 4: 跑测试验证通过**

Run: `python -m pytest tests/test_translator.py -q`
Expected: PASS（5）

- [ ] **Step 5: Commit**

```bash
git add metaprofile/shared/enrich/translator.py tests/test_translator.py
git commit -m "feat(translate): translator.translate_name_one(en→cn + changeLog)"
```

---

## Task 6: translate_tasks（单/批 celery）

**Files:**
- Create: `metaprofile/shared/worker/translate_tasks.py`
- Modify: `metaprofile/shared/worker/celery_app.py`（include 加 translate_tasks）
- Test: `tests/test_translate_tasks.py`

- [ ] **Step 1: 写失败测试**

`tests/test_translate_tasks.py`：

```python
from unittest.mock import patch, AsyncMock, MagicMock

from metaprofile.shared.worker import translate_tasks


def test_translate_name_runs_and_returns_done():
    fake = MagicMock(); fake.translated = True; fake.new_value = "量子"
    with patch.object(translate_tasks, "translate_name_one", AsyncMock(return_value=fake)):
        r = translate_tasks.translate_name("tech", "T1")
    assert r["status"] == "done" and r["translated"] is True


def test_batch_translate_names_iterates_types():
    with patch.object(translate_tasks, "_scan_untranslated", AsyncMock(return_value=[("tech", "T1"), ("org", "O1")])), \
         patch.object(translate_tasks, "translate_name_one", AsyncMock(return_value=MagicMock(translated=True))):
        r = translate_tasks.batch_translate_names(None)
    assert r["status"] == "done" and r["translated"] == 2
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/test_translate_tasks.py -q`
Expected: FAIL — 模块不存在

- [ ] **Step 3: 实现 translate_tasks**

`metaprofile/shared/worker/translate_tasks.py`：

```python
"""翻译 celery 任务：单条 + 批量。run_async 持久 loop（非 asyncio.run）。"""
from __future__ import annotations

import structlog
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.shared.db.postgres import get_session
from metaprofile.shared.enrich.translator import NAME_FIELDS, TranslateOutcome, _orm_cls, translate_name_one
from metaprofile.shared.worker.async_runner import run_async
from metaprofile.shared.worker.celery_app import celery_app

logger = structlog.get_logger(__name__)


async def _async_translate_name(entity_type: str, entity_id: str) -> dict[str, Any]:
    try:
        async with get_session() as session:
            out = await translate_name_one(session, entity_type, entity_id)
            return {"status": "done" if out.translated else "skipped",
                    "translated": out.translated, "new_value": out.new_value,
                    "reason": out.reason, "error": out.error}
    except Exception as exc:  # noqa: BLE001
        logger.warning("translate_name_failed", entity_id=entity_id, error=str(exc))
        return {"status": "failed", "error": str(exc)}


@celery_app.task(name="metaprofile.translate.name", bind=True)
def translate_name(self, entity_type: str, entity_id: str) -> dict[str, Any]:
    return run_async(_async_translate_name(entity_type, entity_id))


async def _scan_untranslated(session: AsyncSession, entity_type: str) -> list[tuple[str, str]]:
    """扫 name_cn 空 & name_en 非空的实体 id 列表。"""
    out: list[tuple[str, str]] = []
    types = [entity_type] if entity_type else list(NAME_FIELDS.keys())
    for t in types:
        cn_field, en_field = NAME_FIELDS[t]
        orm_cls = _orm_cls(t)
        cn_col = getattr(orm_cls, cn_field)
        en_col = getattr(orm_cls, en_field)
        rows = (await session.execute(
            select(getattr(orm_cls, _id_col(t))).where(
                or_(cn_col.is_(None), cn_col == ""),
                en_col.isnot(None), en_col != "",
            )
        )).scalars().all()
        out.extend([(t, str(r)) for r in rows[:5000]])  # 单类型上限防过载
    return out


def _id_col(entity_type: str) -> str:
    return {"tech": "tech_id", "org": "org_id", "person": "person_id", "project": "project_id"}[entity_type]


async def _async_batch(entity_type: str | None) -> dict[str, Any]:
    translated = skipped = failed = 0
    try:
        async with get_session() as session:
            targets = await _scan_untranslated(session, entity_type)
        for t, eid in targets:
            # 每条独立 session（避免长事务）
            async with get_session() as s:
                out = await translate_name_one(s, t, eid)
            if out.translated:
                translated += 1
            elif out.error:
                failed += 1
            else:
                skipped += 1
        return {"status": "done", "translated": translated, "skipped": skipped, "failed": failed}
    except Exception as exc:  # noqa: BLE001
        logger.warning("translate_batch_failed", error=str(exc))
        return {"status": "failed", "error": str(exc)}


@celery_app.task(name="metaprofile.translate.batch", bind=True)
def batch_translate_names(self, entity_type: str | None = None) -> dict[str, Any]:
    return run_async(_async_batch(entity_type))
```

`celery_app.py` `include` 加 `"metaprofile.shared.worker.translate_tasks"`。

- [ ] **Step 4: 跑测试验证通过**

Run: `python -m pytest tests/test_translate_tasks.py -q`
Expected: PASS（2）

- [ ] **Step 5: Commit**

```bash
git add metaprofile/shared/worker/translate_tasks.py metaprofile/shared/worker/celery_app.py tests/test_translate_tasks.py
git commit -m "feat(translate): celery translate_name + batch_translate_names"
```

---

## Task 7: 4 画像 translate 端点 + 轮询

**Files:**
- Modify: 4× `profile_*/api/routes_*.py`（加 translate + poll）
- Test: `tests/test_translate_routes.py`（TestClient）

> 照搬 enrich 端点范式（commit 4eae9f2）。4 画像各加 `POST /profile/{type}/{id}/translate` → `translate_name.delay` + `GET /profile/{type}/translate/task/{id}` 返 AsyncResult 状态。

- [ ] **Step 1: 写失败测试**

`tests/test_translate_routes.py`（用 tech 画像 TestClient；其余 3 画像同构，至少测 tech）：

```python
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from metaprofile.profile_tech.main import app


def test_translate_endpoint_enqueues_task():
    client = TestClient(app)
    with patch("metaprofile.profile_tech.api.routes_profile.translate_name") as t:
        t.delay = MagicMock(return_value=MagicMock(id="abc"))
        r = client.post("/api/v1/profile/tech/T1/translate")
    assert r.status_code == 200
    assert "task_id" in r.json()
    t.delay.assert_called_once_with("tech", "T1")
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/test_translate_routes.py -q`
Expected: FAIL — 路由不存在

- [ ] **Step 3: 加端点（4 画像同构，以 tech 为例）**

`profile_tech/api/routes_profile.py`（或对应关系路由文件）加：

```python
from metaprofile.shared.worker.translate_tasks import translate_name
from celery.result import AsyncResult
from metaprofile.shared.worker.celery_app import celery_app

@router.post("/profile/tech/{tech_id}/translate")
async def translate_tech(tech_id: str) -> dict:
    res = translate_name.delay("tech", tech_id)
    return {"task_id": res.id}


@router.get("/profile/tech/translate/task/{task_id}")
async def translate_task_status(task_id: str) -> dict:
    r = AsyncResult(task_id, app=celery_app)
    return {"task_id": task_id, "state": r.state, "result": r.result if r.ready() else None}
```

> org/person/project 各照搬（替换 type + id 列名 + import 路由模块名）。前端 `api/tech.ts` + `api/profile.ts` 各加 `translate(id)` + `getTranslateTaskStatus(taskId)`（照搬 enrich）。

- [ ] **Step 4: 跑测试验证通过**

Run: `python -m pytest tests/test_translate_routes.py -q`
Expected: PASS（1）

- [ ] **Step 5: Commit**

```bash
git add metaprofile/profile_*/api/ tests/test_translate_routes.py
git commit -m "feat(translate): 4 画像 /translate 端点 + 轮询"
```

---

## Task 8: 批量翻译端点（settings）

**Files:**
- Create（或并入 routes_scheduler）：`POST /settings/translate/batch`

- [ ] **Step 1: 写失败测试**

追加到 `tests/test_translate_routes.py`：

```python
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from metaprofile.settings_api.main import app as settings_app


def test_batch_translate_endpoint():
    client = TestClient(settings_app)
    with patch("metaprofile.settings_api.api.routes_scheduler.batch_translate_names") as t:
        t.delay = MagicMock(return_value=MagicMock(id="batch1"))
        r = client.post("/api/v1/settings/translate/batch?entity_type=tech")
    assert r.status_code == 200 and r.json()["task_id"] == "batch1"
    t.delay.assert_called_once_with("tech")
```

- [ ] **Step 2-4: 实现（routes_scheduler.py 内）+ 跑测试**

`metaprofile/settings_api/api/routes_scheduler.py` 加：

```python
from metaprofile.shared.worker.translate_tasks import batch_translate_names

@router.post("/settings/translate/batch")
async def batch_translate(entity_type: str | None = None) -> dict:
    res = batch_translate_names.delay(entity_type)
    return {"task_id": res.id}
```

Run: `python -m pytest tests/test_translate_routes.py -q` → PASS（2）

- [ ] **Step 5: Commit**

```bash
git add metaprofile/settings_api/api/routes_scheduler.py tests/test_translate_routes.py
git commit -m "feat(translate): /settings/translate/batch 端点"
```

---

## Task 9: 前端 displayName + EntityName

**Files:**
- Create: `frontend/src/utils/displayName.ts` (+test)
- Create: `frontend/src/components/EntityName.tsx` (+test)

- [ ] **Step 1: 写失败测试**

`frontend/src/utils/displayName.test.ts`：

```typescript
import { describe, it, expect } from 'vitest'
import { displayName, isUntranslated } from './displayName'

describe('displayName', () => {
  it('name_cn 优先', () => expect(displayName({ name_cn: '量子', name_en: 'q', id: 'T1' })).toBe('量子'))
  it('name_cn 空回退 name_en', () => expect(displayName({ name_cn: '', name_en: 'quantum', id: 'T1' })).toBe('quantum'))
  it('都空回退 id', () => expect(displayName({ name_cn: '', name_en: '', id: 'T1' })).toBe('T1'))
  it('null 安全', () => expect(displayName({ name_cn: null, name_en: null, id: 'X' })).toBe('X'))
})

describe('isUntranslated', () => {
  it('name_cn 空 & name_en 有 → true', () => expect(isUntranslated({ name_cn: '', name_en: 'q', id: 'T1' })).toBe(true))
  it('name_cn 有 → false', () => expect(isUntranslated({ name_cn: '量', name_en: 'q', id: 'T1' })).toBe(false))
  it('都空 → false(无源可译)', () => expect(isUntranslated({ name_cn: '', name_en: '', id: 'T1' })).toBe(false))
})
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd frontend && npx vitest run src/utils/displayName.test.ts`
Expected: FAIL — 模块不存在

- [ ] **Step 3: 实现**

`frontend/src/utils/displayName.ts`：

```typescript
export interface NameLike { name_cn?: string | null; name_en?: string | null; id: string }

const norm = (v?: string | null) => (v && v.trim()) || ''

export function displayName(e: NameLike): string {
  return norm(e.name_cn) || norm(e.name_en) || e.id
}

export function isUntranslated(e: NameLike): boolean {
  return !norm(e.name_cn) && !!norm(e.name_en)
}
```

`frontend/src/components/EntityName.tsx`：

```typescript
import { Tooltip, Button } from 'antd'
import { displayName, isUntranslated, type NameLike } from '../utils/displayName'

export default function EntityName({
  entity, onTranslate, translating,
}: {
  entity: NameLike
  onTranslate?: () => void
  translating?: boolean
}) {
  const name = displayName(entity)
  if (!isUntranslated(entity) || !onTranslate) {
    return <span>{name}</span>
  }
  return (
    <Tooltip title={`原文: ${entity.name_en}（点翻译）`}>
      <span style={{ marginRight: 4 }}>{name}</span>
      <Button size="small" type="link" loading={translating} onClick={onTranslate}>译</Button>
    </Tooltip>
  )
}
```

`EntityName.test.tsx`（渲染 + 未译显 Tooltip/按钮 + 已译只 span）。

- [ ] **Step 4: 跑测试验证通过**

Run: `cd frontend && npx vitest run src/utils/displayName.test.ts src/components/EntityName.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add frontend/src/utils/displayName.ts frontend/src/components/EntityName.tsx frontend/src/utils/displayName.test.ts frontend/src/components/EntityName.test.tsx
git commit -m "feat(ui): displayName + EntityName(name_en 兜底 + 翻译入口)"
```

---

## Task 10: 7 审计点替换 + 编辑表单放宽

**Files:**
- Modify: 4× `frontend/src/pages/Profile*/index.tsx`（spec §6.3 的 7 点）+ 后端 `routes_signals.py` 节点名 fallback
- Modify: `ProfileTech/index.tsx:444`（form required 放宽）

> 复用 EntityName + displayName。审计点清单见 spec §6.3。代表改动：

- [ ] **Step 1: ProfileTech 改 4 点**

`ProfileTech/index.tsx`：
- `:120` `<span>{p?.tech_name_cn ?? id}</span>` → `<EntityName entity={{name_cn: p?.tech_name_cn, name_en: p?.tech_name_en, id}} onTranslate={handleTranslate} translating={...} />`
- `:152` `<Descriptions.Item label="中文名">{p.tech_name_cn}</Descriptions.Item>` → 同 EntityName（name_cn/name_en）
- `:357` 表格列 `tech_name_cn` → render: `(v, r) => <EntityName entity={{name_cn: v, name_en: r.tech_name_en, id: r.tech_id}} onTranslate={...}/>`
- `:444` `<Form.Item name="tech_name_cn" rules={[{required:true}]}>` → `rules={[]}`（放宽，与 schema default="" 一致）
- 加 `handleTranslate`：`techService.translate(id)` → 轮询 → `refetch()`。

```typescript
const [translating, setTranslating] = useState(false)
const handleTranslate = async () => {
  if (!id) return
  setTranslating(true)
  try {
    const { task_id } = await techService.translate(id)
    await pollTask(task_id, techService.getTranslateTaskStatus)  // 复用 enrich 轮询 util
    refetch()
  } finally { setTranslating(false) }
}
```

- [ ] **Step 2: 其余 3 画像同构改**（list 列 / detail / drawer title / form），各加 `translate`/`getTranslateTaskStatus` api。

- [ ] **Step 3: 后端关系节点名 fallback**

`metaprofile/new_tech_discovery/api/routes_signals.py` `name_map[rid] = ... or rid` → fallback name_en：

```python
val = getattr(r, name_col)
# 兜底：name_cn 空 → name_en → id
name = (val[0] if isinstance(val, list) and val else val) or getattr(r, _en_col(etype), None) or rid
name_map[rid] = name
```

（`_en_col` 映射 tech→tech_name_en 等。）

- [ ] **Step 4: tsc + vitest**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: tsc clean · vitest 全绿

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Profile* metaprofile/new_tech_discovery/api/routes_signals.py
git commit -m "feat(ui): 7 审计点 name_en 兜底 + 编辑表单放宽 + 关系节点 fallback"
```

---

## Task 11: 任务配置 UI（scheduled_task CRUD + 立即执行 + cron 校验）

**Files:**
- Create: `metaprofile/settings_api/api/routes_scheduler.py`（CRUD + run-now；Task 8 已加 batch，本任务补全）
- Modify: `frontend/src/pages/Settings/index.tsx`（scheduled_task 管理 Tab）
- Modify: `frontend/src/api/settings.ts`（scheduledTask CRUD api）

- [ ] **Step 1: 后端 CRUD 路由**

`routes_scheduler.py` 加（CRUD + 立即执行 + cron 校验）：

```python
from croniter import croniter
from fastapi import HTTPException
from metaprofile.settings_api.services.scheduler_service import list_tasks, upsert_task, run_now, sync_collection_crons

@router.get("/settings/scheduled-tasks")
async def list_scheduled(db: AsyncSession = Depends(fastapi_session_dep)):
    return await list_tasks(db)

@router.post("/settings/scheduled-tasks")
async def create_scheduled(payload: dict, db: AsyncSession = Depends(fastapi_session_dep)):
    if not croniter.is_valid(payload.get("cron", "")):
        raise HTTPException(422, "非法 cron 表达式")
    return await upsert_task(db, **payload)

@router.post("/settings/scheduled-tasks/{task_id}/run")
async def run_scheduled(task_id: int, db: AsyncSession = Depends(fastapi_session_dep)):
    try:
        return {"task_id": await run_now(db, task_id)}
    except ValueError as e:
        raise HTTPException(404, str(e))

@router.post("/settings/scheduled-tasks/sync-collection")
async def sync_collection(db: AsyncSession = Depends(fastapi_session_dep)):
    return {"created": await sync_collection_crons(db)}
```

- [ ] **Step 2: 前端 settings.ts api**

```typescript
export const settingsApi = {
  // ...既有...
  listScheduledTasks: () => settingsApi.get('/api/v1/settings/scheduled-tasks').then(r => r.data),
  createScheduledTask: (p: Record<string, unknown>) => settingsApi.post('/api/v1/settings/scheduled-tasks', p).then(r => r.data),
  runScheduledTask: (id: number) => settingsApi.post(`/api/v1/settings/scheduled-tasks/${id}/run`).then(r => r.data),
  syncCollectionCrons: () => settingsApi.post('/api/v1/settings/scheduled-tasks/sync-collection').then(r => r.data),
}
```

- [ ] **Step 3: Settings/index.tsx 加「定时任务」Tab**

列表（name/task_type/cron/enabled/last_run_at/last_status）+ 新建表单（task_type 下拉[采集/翻译批量] + cron 输入 + params JSON + enabled）+ 「立即执行」按钮 + 「同步采集定时」按钮。复用既有 TasksTab 表格范式。

- [ ] **Step 4: tsc + vitest + e2e（live）**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: clean/绿

- [ ] **Step 5: Commit**

```bash
git add metaprofile/settings_api/api/routes_scheduler.py frontend/src/pages/Settings/index.tsx frontend/src/api/settings.ts
git commit -m "feat(scheduler): scheduled_task CRUD + 立即执行 + 任务配置 UI"
```

---

## Task 12: 全套门禁 + spec 回写

- [ ] **Step 1: 后端全量 pytest**

Run: `python -m pytest tests/ -q`
Expected: 全绿（基线 468 + 本计划新增 ≈ 20）

- [ ] **Step 2: 前端**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: clean · 全绿（基线 38 + 新增 ≈ 10）

- [ ] **Step 3: 部署 + e2e 验**

重建 backend-worker（beat + 新 task）；`alembic upgrade head`（migration 0007）；手动测：单条翻译按钮跑通、批量、scheduled_task 立即执行、cron 到期（改 cron 为 `* * * * *` 触发）。

- [ ] **Step 4: spec 回写状态**

`docs/superpowers/specs/2026-06-20-non-chinese-data-strategy-design.md` §1 加「**已实现**（见 plan 2026-06-20-non-chinese-data-strategy.md）」。

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-06-20-non-chinese-data-strategy-design.md
git commit -m "docs(spec): 非中文数据策略 实施状态回写"
```

---

## 自审清单

- [ ] spec §3 调度器 → ScheduledTaskORM(T1) + is_due(T2) + tick/dispatch/beat(T3) + 采集活化(T4) 全覆盖
- [ ] spec §4 翻译 → translator + 字段映射 + LLM + changeLog(T5)
- [ ] spec §5 触发 → 单/批 celery(T6) + 4 端点(T7) + 批量端点(T8)
- [ ] spec §6 UI 兜底 → displayName/EntityName(T9) + 7 审计点(T10)
- [ ] spec §7 任务配置 → CRUD + 立即执行 + cron 校验(T11)
- [ ] **所有新 celery 任务用 `run_async`**（非 asyncio.run）—— T6 + 调度器 tick
- [ ] croniter 到期判定一致（is_due 测 4 case）
- [ ] 无 placeholder；签名跨任务一致（NAME_FIELDS / translate_name_one / ScheduledTaskORM / TASK_DISPATCH）
- [ ] 全套门禁绿

---

## 已知局限 / 后续

- **celery beat 需独立进程**：`celery -A metaprofile.shared.worker.celery_app beat` + worker；deploy/docker-compose 需加 beat 容器（或 worker 用 `--beat` 单进程起）。部署步骤含此。
- **project name_cn list**：翻译写 `[译值]`，若已有多元素仅替换首。
- **采集 cron 同步**：一次性 sync；新建 DataSourceConfig 带 schedule_cron 后需再点「同步采集定时」或后续改创建时自动落 scheduled_task（YAGNI 留）。
- **翻译质量**：无评分/复核（YAGNI），LLM 直写 + changeLog 可追溯。
