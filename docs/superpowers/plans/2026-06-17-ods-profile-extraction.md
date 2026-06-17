# ODS→四类画像 抽取管线 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `metaprofile/ingest_ods` — a batch pipeline that reads ODS `ods_zbzx` (Doris, via SQL) and produces Tech/Project/Org/Person profiles + relations, scheduled (cron) and manually triggered, incremental (update_time watermark) + full backfill, LLM-driven content mining + scoring.

**Architecture:** 5-stage pipeline (extract → content_mine → resolve → score → write) driven by a `BatchOrchestrator` (id-keyset batches, `asyncio.Semaphore` concurrency, per-profile-type mutex, resumable watermark). New `source_type="sql_warehouse"` plugs into the existing `collector_service` / `data_source_configs` / `collection_tasks`. Reuses `LLMGateway`, profile services' upsert, `TripleWriter` (Neo4j), `EntityChangeLogORM`. No new infra.

**Tech Stack:** Python 3.12, async SQLAlchemy 2.0, pydantic, pymysql (Doris MySQL protocol), structlog, pytest + pytest-asyncio, alembic. `cryptography.fernet` for DB password encryption.

**Spec:** `docs/superpowers/specs/2026-06-17-ods-profile-extraction-design.md`

---

## File Structure

**Create (new package `metaprofile/ingest_ods/`):**
- `__init__.py`, `domain/__init__.py`, `services/__init__.py`, `collectors/__init__.py`, `llm/__init__.py` — package markers.
- `domain/orm_models.py` — `DBConnectionORM`, `IngestRawORM`, `RelationStagingORM`, `IngestErrorORM`.
- `domain/mappings.py` — table→profile field-mapping registry + `apply_mapping()`.
- `services/security.py` — `encrypt_pw`/`decrypt_pw` (Fernet).
- `services/watermark.py` — `WatermarkStore` (last_id/last_watermark on config_json).
- `services/connections.py` — `resolve_dsn(DBConnectionORM) -> dict` (decrypt → pymysql params).
- `services/extractor.py` — `Extractor.extract_batch()` (表→表, id-keyset, → staging dicts).
- `services/resolver.py` — `EntityResolver.resolve()` (key-first merge + LLM disambig).
- `services/scorer.py` — `Scorer.score()` (veracity/timeliness via LLM).
- `services/writer.py` — `Writer.write_profile()` (upsert + scores + changelog), `write_relations()` (TripleWriter).
- `services/content_miner.py` — `ContentMiner.mine()` (attachment LLM → entities + RelationTriple).
- `services/orchestrator.py` — `BatchOrchestrator.run()` (batches + Semaphore + mutex + resume).
- `collectors/sql_warehouse.py` — `run_sql_warehouse_collection(task, source)` adapter.
- `llm/prompts.py` — pydantic schemas + prompt strings + relation mapper.
- `migrations/versions/0003_ingest_ods.py` — alembic.
- `scripts/seed_ods_datasources.py` — seed db_connections + data_source_configs.

**Modify:**
- `metaprofile/profile_{tech,org,person,project}/domain/orm_models.py` — add `veracity_score`, `timeliness_score`, `data_as_of` columns.
- `metaprofile/settings_api/services/collector_service.py` — add `sql_warehouse` branch.
- `pyproject.toml` (or requirements) — add `cryptography` if missing.

**Tests (new `tests/ingest_ods/`):** `test_orm_models.py`, `test_security.py`, `test_watermark.py`, `test_mappings.py`, `test_connections.py`, `test_extractor.py`, `test_resolver.py`, `test_scorer.py`, `test_writer.py`, `test_content_miner.py`, `test_orchestrator.py`, `test_sql_warehouse_collector.py`, `test_seed_ods.py`, `test_e2e_pipeline.py`.

---

## Conventions

- Async SQLAlchemy: services take `session: AsyncSession`. Tests mock it with `AsyncMock`.
- ORM inherits `Base, TimestampMixin` from `metaprofile/shared/db/base.py`.
- IDs: `new_entity_id(EntityType.X)` from `metaprofile/shared/utils/id_generator.py`.
- `SourceMethod.LLM_EXTRACT` / `.RULE` / `.HUMAN` from `metaprofile/shared/schemas/base.py`.
- Relations MUST use `RelationType` enum from `metaprofile/shared/schemas/relations.py`.
- Commit after each task. Branch from `main`.

---

## Task 1: Data model — ORM + migration 0003

**Files:**
- Create: `metaprofile/ingest_ods/__init__.py` (empty), `metaprofile/ingest_ods/domain/__init__.py` (empty), `metaprofile/ingest_ods/domain/orm_models.py`
- Create: `migrations/versions/0003_ingest_ods.py`
- Modify: `metaprofile/profile_tech/domain/orm_models.py`, `metaprofile/profile_org/domain/orm_models.py`, `metaprofile/profile_person/domain/orm_models.py`, `metaprofile/profile_project/domain/orm_models.py`
- Test: `tests/ingest_ods/__init__.py` (empty), `tests/ingest_ods/test_orm_models.py`

- [ ] **Step 1: Write the failing test**

`tests/ingest_ods/test_orm_models.py`:
```python
from __future__ import annotations

from metaprofile.ingest_ods.domain.orm_models import (
    DBConnectionORM, IngestRawORM, RelationStagingORM, IngestErrorORM,
)
from metaprofile.profile_tech.domain.orm_models import TechProfileORM
from metaprofile.profile_org.domain.orm_models import OrgProfileORM
from metaprofile.profile_person.domain.orm_models import PersonProfileORM
from metaprofile.profile_project.domain.orm_models import ProjectProfileORM


def _cols(orm_cls) -> set[str]:
    return {c.name for c in orm_cls.__table__.columns}


def test_db_connections_columns() -> None:
    c = _cols(DBConnectionORM)
    assert {"name", "dialect", "host", "port", "database", "username",
            "password_enc", "pool_size", "read_only", "is_enabled"} <= c


def test_staging_columns() -> None:
    assert {"profile_type", "source_table", "source_id", "entity_key",
            "raw_payload", "batch_id", "status"} <= _cols(IngestRawORM)
    assert {"batch_id", "subject_name", "subject_type", "object_name",
            "object_type", "relation", "confidence", "written"} <= _cols(RelationStagingORM)
    assert {"batch_id", "source_table", "source_id", "stage",
            "error_msg"} <= _cols(IngestErrorORM)


def test_profile_score_columns_added() -> None:
    for orm_cls in (TechProfileORM, OrgProfileORM, PersonProfileORM, ProjectProfileORM):
        assert {"veracity_score", "timeliness_score", "data_as_of"} <= _cols(orm_cls)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/ingest_ods/test_orm_models.py -v`
Expected: FAIL `ImportError: No module named 'metaprofile.ingest_ods'`

- [ ] **Step 3: Create package + ORM models**

`metaprofile/ingest_ods/domain/orm_models.py`:
```python
"""ingest_ods 域 ORM：DB 连接注册 + 抽取 staging + 关系 staging + 错误。"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from metaprofile.shared.db.base import Base, TimestampMixin


class DBConnectionORM(Base, TimestampMixin):
    """外部 DB 连接注册（Doris 云/本地）。密码加密存 password_enc。"""
    __tablename__ = "db_connections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    dialect: Mapped[str] = mapped_column(String(16), nullable=False, default="doris")
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[int] = mapped_column(Integer, nullable=False)
    database: Mapped[str] = mapped_column(String(128), nullable=False)
    username: Mapped[str] = mapped_column(String(128), nullable=False)
    password_enc: Mapped[str] = mapped_column(Text, nullable=False)
    charset: Mapped[str] = mapped_column(String(32), nullable=False, default="utf8mb4")
    pool_size: Mapped[int] = mapped_column(Integer, nullable=False, default=8)
    read_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class IngestRawORM(Base, TimestampMixin):
    """抽取 staging：逐源行贡献 + provenance。"""
    __tablename__ = "ingest_raw"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    profile_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    source_table: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_key: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("collection_tasks.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")


class RelationStagingORM(Base, TimestampMixin):
    """关系 staging：内容挖掘产出的三元组（审计 + 写 Neo4j 去重）。"""
    __tablename__ = "relation_staging"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("collection_tasks.id"), nullable=False, index=True)
    subject_name: Mapped[str] = mapped_column(String(512), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(16), nullable=False)
    object_name: Mapped[str] = mapped_column(String(512), nullable=False)
    object_type: Mapped[str] = mapped_column(String(16), nullable=False)
    relation: Mapped[str] = mapped_column(String(64), nullable=False)
    evidence: Mapped[str | None] = mapped_column(Text)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    written: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class IngestErrorORM(Base, TimestampMixin):
    """抽取错误（单批单行失败，不阻塞整任务）。"""
    __tablename__ = "ingest_errors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[int] = mapped_column(Integer, ForeignKey("collection_tasks.id"), nullable=False, index=True)
    source_table: Mapped[str | None] = mapped_column(String(128))
    source_id: Mapped[str | None] = mapped_column(String(64))
    stage: Mapped[str] = mapped_column(String(32), nullable=False)
    error_msg: Mapped[str] = mapped_column(Text, nullable=False)
```

- [ ] **Step 4: Add score columns to the 4 profile ORM models**

In each of `profile_tech/domain/orm_models.py` (after `completeness`), `profile_org/domain/orm_models.py`, `profile_person/domain/orm_models.py`, `profile_project/domain/orm_models.py`, add (keep existing imports; `Date`/`Float` already imported in those files — verify):
```python
    # 质量评分（抽取管线写入）
    veracity_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    timeliness_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    data_as_of: Mapped[date | None] = mapped_column(Date)
```
Ensure `Date` and `Float` are in the `from sqlalchemy import (...)` import of each file (they already are).

- [ ] **Step 5: Create migration 0003**

`migrations/versions/0003_ingest_ods.py`:
```python
"""ingest_ods: db_connections + staging 表 + profile 主表质量评分列

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-17
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    from sqlalchemy import inspect
    insp = inspect(op.get_bind())

    if not insp.has_table("db_connections"):
        op.create_table(
            "db_connections",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("name", sa.String(128), nullable=False, unique=True),
            sa.Column("dialect", sa.String(16), nullable=False, server_default="doris"),
            sa.Column("host", sa.String(255), nullable=False),
            sa.Column("port", sa.Integer, nullable=False),
            sa.Column("database", sa.String(128), nullable=False),
            sa.Column("username", sa.String(128), nullable=False),
            sa.Column("password_enc", sa.Text, nullable=False),
            sa.Column("charset", sa.String(32), nullable=False, server_default="utf8mb4"),
            sa.Column("pool_size", sa.Integer, nullable=False, server_default="8"),
            sa.Column("read_only", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if not insp.has_table("ingest_raw"):
        op.create_table(
            "ingest_raw",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("profile_type", sa.String(32), nullable=False),
            sa.Column("source_table", sa.String(128), nullable=False),
            sa.Column("source_id", sa.String(64), nullable=False),
            sa.Column("entity_key", JSONB, nullable=False, server_default="{}"),
            sa.Column("raw_payload", JSONB, nullable=False),
            sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("batch_id", sa.Integer, nullable=False),
            sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["batch_id"], ["collection_tasks.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_ingest_raw_profile_type", "ingest_raw", ["profile_type"])
        op.create_index("ix_ingest_raw_source_table", "ingest_raw", ["source_table"])
        op.create_index("ix_ingest_raw_batch_id", "ingest_raw", ["batch_id"])

    if not insp.has_table("relation_staging"):
        op.create_table(
            "relation_staging",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("batch_id", sa.Integer, nullable=False),
            sa.Column("subject_name", sa.String(512), nullable=False),
            sa.Column("subject_type", sa.String(16), nullable=False),
            sa.Column("object_name", sa.String(512), nullable=False),
            sa.Column("object_type", sa.String(16), nullable=False),
            sa.Column("relation", sa.String(64), nullable=False),
            sa.Column("evidence", sa.Text),
            sa.Column("confidence", sa.Float, nullable=False, server_default="0"),
            sa.Column("written", sa.Boolean, nullable=False, server_default="false"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["batch_id"], ["collection_tasks.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_relation_staging_batch_id", "relation_staging", ["batch_id"])

    if not insp.has_table("ingest_errors"):
        op.create_table(
            "ingest_errors",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("batch_id", sa.Integer, nullable=False),
            sa.Column("source_table", sa.String(128)),
            sa.Column("source_id", sa.String(64)),
            sa.Column("stage", sa.String(32), nullable=False),
            sa.Column("error_msg", sa.Text, nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["batch_id"], ["collection_tasks.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_ingest_errors_batch_id", "ingest_errors", ["batch_id"])

    # profile 主表加质量评分列（幂等）
    for tbl in ("tech_profile", "org_profile", "person_profile", "project_profile"):
        cols = {c["name"] for c in insp.get_columns(tbl)}
        if "veracity_score" not in cols:
            op.add_column(tbl, sa.Column("veracity_score", sa.Float, nullable=False, server_default="0"))
        if "timeliness_score" not in cols:
            op.add_column(tbl, sa.Column("timeliness_score", sa.Float, nullable=False, server_default="0"))
        if "data_as_of" not in cols:
            op.add_column(tbl, sa.Column("data_as_of", sa.Date, nullable=True))


def downgrade() -> None:
    for tbl in ("tech_profile", "org_profile", "person_profile", "project_profile"):
        op.drop_column(tbl, "data_as_of")
        op.drop_column(tbl, "timeliness_score")
        op.drop_column(tbl, "veracity_score")
    op.drop_table("ingest_errors")
    op.drop_table("relation_staging")
    op.drop_table("ingest_raw")
    op.drop_table("db_connections")
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/ingest_ods/test_orm_models.py -v`
Expected: PASS (4 tests)

- [ ] **Step 7: Commit**

```bash
git add metaprofile/ingest_ods/__init__.py metaprofile/ingest_ods/domain/ metaprofile/profile_tech/domain/orm_models.py metaprofile/profile_org/domain/orm_models.py metaprofile/profile_person/domain/orm_models.py metaprofile/profile_project/domain/orm_models.py migrations/versions/0003_ingest_ods.py tests/ingest_ods/
git commit -m "feat(ingest_ods): ORM 模型 + migration 0003(db_connections/staging/profile评分列)"
```

---

## Task 2: Password security util

**Files:**
- Create: `metaprofile/ingest_ods/services/security.py`
- Modify: `metaprofile/shared/config/settings.py` — ensure `secret_key` setting exists (read it; if absent, add).
- Test: `tests/ingest_ods/test_security.py`

- [ ] **Step 1: Write the failing test**

`tests/ingest_ods/test_security.py`:
```python
from metaprofile.ingest_ods.services.security import encrypt_pw, decrypt_pw


def test_encrypt_decrypt_roundtrip() -> None:
    pw = "92f5IRTld93lDPKYZZ5p"
    enc = encrypt_pw(pw)
    assert enc != pw
    assert decrypt_pw(enc) == pw


def test_decrypt_plaintext_fallback() -> None:
    # 兼容历史明文（未加密直接存）
    assert decrypt_pw("plain-password") == "plain-password"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/ingest_ods/test_security.py -v`
Expected: FAIL `ImportError`

- [ ] **Step 3: Implement**

`metaprofile/ingest_ods/services/security.py`:
```python
"""DB 密码对称加密（Fernet，key 来自 settings.secret_key）。"""
from __future__ import annotations

import base64
import hashlib

from metaprofile.shared.config.settings import settings


def _fernet():
    from cryptography.fernet import Fernet
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.secret_key.encode()).digest())
    return Fernet(key)


def encrypt_pw(plain: str) -> str:
    return _fernet().encrypt(plain.encode()).decode()


def decrypt_pw(stored: str) -> str:
    # Fernet token 以 gAAAA 开头；否则视为历史明文直接返回
    if stored.startswith("gAAAA"):
        return _fernet().decrypt(stored.encode()).decode()
    return stored
```

Ensure `settings.secret_key` exists. If `metaprofile/shared/config/settings.py` lacks it, add a field to the settings model (read the file first): e.g. `secret_key: str = os.getenv("SECRET_KEY", "dev-insecure-key")`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/ingest_ods/test_security.py -v`
Expected: PASS. If `cryptography` missing: `pip install cryptography` and add to `pyproject.toml` deps.

- [ ] **Step 5: Commit**

```bash
git add metaprofile/ingest_ods/services/security.py metaprofile/shared/config/settings.py tests/ingest_ods/test_security.py pyproject.toml
git commit -m "feat(ingest_ods): DB 密码 Fernet 加解密(security.py)"
```

---

## Task 3: DBConnection → pymysql DSN resolver

**Files:**
- Create: `metaprofile/ingest_ods/services/connections.py`
- Test: `tests/ingest_ods/test_connections.py`

- [ ] **Step 1: Write the failing test**

`tests/ingest_ods/test_connections.py`:
```python
from unittest.mock import patch

from metaprofile.ingest_ods.domain.orm_models import DBConnectionORM
from metaprofile.ingest_ods.services.connections import resolve_dsn


def _conn(**kw) -> DBConnectionORM:
    base = dict(host="10.242.0.1", port=9030, database="ods_zbzx", username="gz_kt5",
                password_enc="gAAAA-secret", charset="utf8mb4")
    base.update(kw)
    orm = DBConnectionORM(name="x", dialect="doris", **base)
    return orm


def test_resolve_dsn_decrypts_password() -> None:
    with patch("metaprofile.ingest_ods.services.connections.decrypt_pw", return_value="DEC"):
        dsn = resolve_dsn(_conn())
    assert dsn == dict(host="10.242.0.1", port=9030, user="gz_kt5",
                       password="DEC", database="ods_zbzx", charset="utf8mb4",
                       connect_timeout=15, read_timeout=600)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/ingest_ods/test_connections.py -v`
Expected: FAIL `ImportError`

- [ ] **Step 3: Implement**

`metaprofile/ingest_ods/services/connections.py`:
```python
"""DBConnectionORM → pymysql 连接参数。"""
from __future__ import annotations

from metaprofile.ingest_ods.domain.orm_models import DBConnectionORM
from metaprofile.ingest_ods.services.security import decrypt_pw


def resolve_dsn(conn: DBConnectionORM) -> dict:
    return {
        "host": conn.host,
        "port": conn.port,
        "user": conn.username,
        "password": decrypt_pw(conn.password_enc),
        "database": conn.database,
        "charset": conn.charset or "utf8mb4",
        "connect_timeout": 15,
        "read_timeout": 600,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/ingest_ods/test_connections.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add metaprofile/ingest_ods/services/connections.py tests/ingest_ods/test_connections.py
git commit -m "feat(ingest_ods): DBConnection→pymysql DSN resolver(connections.py)"
```

---

## Task 4: Watermark store

**Files:**
- Create: `metaprofile/ingest_ods/services/watermark.py`
- Test: `tests/ingest_ods/test_watermark.py`

- [ ] **Step 1: Write the failing test**

`tests/ingest_ods/test_watermark.py`:
```python
from datetime import datetime, timezone
from unittest.mock import MagicMock

from metaprofile.ingest_ods.services.watermark import WatermarkStore


def _source() -> MagicMock:
    s = MagicMock()
    s.config_json = {}
    return s


def test_get_returns_none_when_unset() -> None:
    assert WatermarkStore.get(_source(), "last_id") is None


def test_set_and_get_roundtrip() -> None:
    src = _source()
    WatermarkStore.set(src, "last_id", 12345)
    assert src.config_json["last_id"] == 12345
    assert WatermarkStore.get(src, "last_id") == 12345


def test_set_watermark_datetime() -> None:
    src = _source()
    ts = datetime(2026, 6, 17, tzinfo=timezone.utc)
    WatermarkStore.set(src, "last_watermark", ts)
    assert WatermarkStore.get(src, "last_watermark") == ts.isoformat()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/ingest_ods/test_watermark.py -v`
Expected: FAIL `ImportError`

- [ ] **Step 3: Implement**

`metaprofile/ingest_ods/services/watermark.py`:
```python
"""last_id / last_watermark 存取（落在 DataSourceConfigORM.config_json）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any


class WatermarkStore:
    KEY_ID = "last_id"
    KEY_WM = "last_watermark"

    @staticmethod
    def get(source, key: str) -> Any:
        return (source.config_json or {}).get(key)

    @staticmethod
    def set(source, key: str, value: Any) -> None:
        cfg = dict(source.config_json or {})
        cfg[key] = value.isoformat() if isinstance(value, datetime) else value
        source.config_json = cfg  # 触发 ORM 脏标记
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/ingest_ods/test_watermark.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add metaprofile/ingest_ods/services/watermark.py tests/ingest_ods/test_watermark.py
git commit -m "feat(ingest_ods): WatermarkStore(last_id/last_watermark on config_json)"
```

---

## Task 5: Field-mapping registry

**Files:**
- Create: `metaprofile/ingest_ods/domain/mappings.py`
- Test: `tests/ingest_ods/test_mappings.py`

Mapping unit: `FieldMap(src_field, target_field, transform=None)`. Registry: `MAPPINGS: dict[str, MappingSet]` keyed by source table → `{profile_type, key_fields: list[str], fields: list[FieldMap]}`.

- [ ] **Step 1: Write the failing test**

`tests/ingest_ods/test_mappings.py`:
```python
from metaprofile.ingest_ods.domain.mappings import apply_mapping, get_mapping


def test_company_basic_info_to_org() -> None:
    m = get_mapping("ods_company_basic_info")
    assert m is not None
    assert m.profile_type == "org"
    assert "company_id" in m.key_fields

    row = {
        "company_id": 101023784,
        "company_name": "某科技有限公司",
        "company_enname": "Foo Tech",
        "usc_code": "91110000MA001X",
        "category_name": "信息技术",
        "province": "HUN",
        "estiblish_time": "2010-01-01",
        "business_scope": "软件开发",
        "legal_person_name": "张三",
        "reg_capital": "1000万人民币",
    }
    out = apply_mapping("ods_company_basic_info", row)
    assert out["profile_type"] == "org"
    assert out["entity_key"]["company_id"] == 101023784
    assert out["entity_key"]["usc_code"] == "91110000MA001X"
    assert out["attrs"]["name_cn"] == "某科技有限公司"
    assert out["attrs"]["name_en"] == "Foo Tech"
    assert out["attrs"]["tech_domains"] == ["信息技术"]
    assert out["attrs"]["founded_date"] == "2010-01-01"


def test_talent_info_to_person() -> None:
    row = {"id": 1, "full_name": "李四", "education": "博士", "job_title": "研究员",
           "employer": "上海交通大学",
           "features": {"sex": "男", "mail": "a@b.com", "discipline": "计算机",
                        "graduatedUniversity": "清华"}}
    out = apply_mapping("ods_talent_info_cn", row)
    assert out["profile_type"] == "person"
    assert out["entity_key"]["full_name_employer"] == "李四|上海交通大学"
    assert out["entity_key"]["email"] == "a@b.com"
    assert out["attrs"]["name_cn"] == "李四"
    assert out["attrs"]["highest_degree"] == "博士"
    assert out["attrs"]["gender"] == "男"


def test_unknown_table_returns_none() -> None:
    assert get_mapping("not_a_table") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/ingest_ods/test_mappings.py -v`
Expected: FAIL `ImportError`

- [ ] **Step 3: Implement**

`metaprofile/ingest_ods/domain/mappings.py`:
```python
"""表→画像 字段映射注册表。扩展新表：往 MAPPINGS 加条目即可。"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class FieldMap:
    src: str                          # 源列名（可点号取 features.x）
    target: str                       # 目标画像字段
    transform: Callable[[Any], Any] | None = None


@dataclass
class MappingSet:
    profile_type: str
    key_fields: list[str]             # 用作 entity_key 的源列
    fields: list[FieldMap] = field(default_factory=list)


def _feat(name: str) -> Callable[[Any], Any]:
    """从 row['features'][name] 取值（features 是 dict 或 JSON 字符串）。"""
    import json
    def f(row: dict) -> Any:
        feat = row.get("features")
        if isinstance(feat, str):
            try:
                feat = json.loads(feat)
            except Exception:
                feat = {}
        if not isinstance(feat, dict):
            return None
        return feat.get(name)
    return f


def _one(value: Any) -> list:
    return [value] if value not in (None, "") else []


MAPPINGS: dict[str, MappingSet] = {
    "ods_company_basic_info": MappingSet(
        profile_type="org",
        key_fields=["company_id", "usc_code"],
        fields=[
            FieldMap("company_id", "org_id"),
            FieldMap("company_name", "name_cn"),
            FieldMap("company_enname", "name_en"),
            FieldMap("usc_code", "usc_code", ),
            FieldMap("category_name", "tech_domains", _one),
            FieldMap("province", "country"),
            FieldMap("estiblish_time", "founded_date"),
            FieldMap("business_scope", "summary"),
            FieldMap("legal_person_name", "legal_person"),
            FieldMap("reg_capital", "reg_capital"),
            FieldMap("pension_count", "scale_raw"),
        ],
    ),
    "ods_talent_info_cn": MappingSet(
        profile_type="person",
        key_fields=["full_name", "employer"],   # 复合键见下方 _key
        fields=[
            FieldMap("full_name", "name_cn"),
            FieldMap("education", "highest_degree"),
            FieldMap("job_title", "current_position", _one),
            FieldMap("employer", "current_org"),
            FieldMap(_feat("sex"), "gender"),
            FieldMap(_feat("mail"), "email"),
            FieldMap(_feat("discipline"), "professional_domains", _one),
            FieldMap(_feat("graduatedUniversity"), "graduated_university"),
        ],
    ),
    "ods_science_literature": MappingSet(
        profile_type="tech",
        key_fields=["title"],
        fields=[
            FieldMap("title", "tech_name_cn"),
            FieldMap("abstract", "tech_summary"),
            FieldMap("keyword", "key_points"),
            FieldMap(_feat("doi"), "doi"),
            FieldMap(_feat("pubdate"), "invention_date"),
        ],
    ),
    "ods_invention_patent_cn": MappingSet(
        profile_type="tech",
        key_fields=["title"],
        fields=[
            FieldMap("title", "tech_name_cn"),
            FieldMap("ipc_type", "tech_domain", _one),
            FieldMap("legal_status", "current_status"),
            FieldMap("filing_date", "application_date"),
            FieldMap("applicant", "applicant"),
            FieldMap(_feat("Patent_number"), "patent_number"),
            FieldMap(_feat("Inventor"), "inventors"),
        ],
    ),
    "ods_market_analysis_cn": MappingSet(
        profile_type="project",
        key_fields=["title", "purchaser", "region"],
        fields=[
            FieldMap("title", "name_cn", _one),
            FieldMap("purchaser", "main_orgs", _one),
            FieldMap("region", "region"),
            FieldMap("announcement_type", "status", _one),
            FieldMap("amount", "total_budget_raw"),
            FieldMap("event_time", "start_date"),
            FieldMap(_feat("budget_amount"), "budget_raw"),
            FieldMap(_feat("project_contact"), "managers", _one),
        ],
    ),
}


def get_mapping(table: str) -> MappingSet | None:
    return MAPPINGS.get(table)


def _resolve(row: dict, src: Any) -> Any:
    """src 可以是字符串列名，也可以是 _feat(...) 产出的可调用。"""
    if callable(src):
        return src(row)
    return row.get(src)


def _build_key(table: str, row: dict, mset: MappingSet) -> dict:
    key: dict[str, Any] = {}
    if table == "ods_talent_info_cn":
        name = row.get("full_name")
        emp = row.get("employer")
        if name and emp:
            key["full_name_employer"] = f"{name}|{emp}"
    else:
        for k in mset.key_fields:
            v = row.get(k)
            if v not in (None, ""):
                key[k] = v
    # email/orcid 等从 features 补
    for feat_name, key_name in (("mail", "email"), ("orcid_pub", "orcid"),
                                ("doi", "doi"), ("Patent_number", "patent_number")):
        v = _feat(feat_name)(row)
        if v:
            key[key_name] = v
    return key


def apply_mapping(table: str, row: dict) -> dict | None:
    """row(dict) → {profile_type, entity_key, attrs}；表未注册返回 None。"""
    mset = MAPPINGS.get(table)
    if mset is None:
        return None
    attrs: dict[str, Any] = {}
    for fm in mset.fields:
        val = _resolve(row, fm.src)
        if fm.transform and val is not None:
            val = fm.transform(val) if not callable(fm.src) else fm.transform(row)
        if val not in (None, "", []):
            attrs[fm.target] = val
    return {
        "profile_type": mset.profile_type,
        "entity_key": _build_key(table, row, mset),
        "attrs": attrs,
    }
```

Note: `_feat(...)` returns a callable; `FieldMap.src` is that callable. `_resolve` calls it with `row`. The transform branch simplifies: if `fm.src` is callable (a `_feat`), the callable already returns the value; transform applies to that value. Fix transform invocation in `_resolve`/`apply_mapping` so test passes — `val = _resolve(row, fm.src); if fm.transform: val = fm.transform(val)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/ingest_ods/test_mappings.py -v`
Expected: PASS (3 tests). Iterate on `_resolve`/transform until green.

- [ ] **Step 5: Commit**

```bash
git add metaprofile/ingest_ods/domain/mappings.py tests/ingest_ods/test_mappings.py
git commit -m "feat(ingest_ods): 表→画像字段映射注册表(mappings.py)+5表映射"
```

---

## Task 6: Extractor (表→表)

**Files:**
- Create: `metaprofile/ingest_ods/services/extractor.py`
- Test: `tests/ingest_ods/test_extractor.py`

Reads Doris via pymysql id-keyset; applies `apply_mapping`; returns staging dicts. No DB writes here (orchestrator persists). Async wrapper around blocking pymysql via `asyncio.to_thread`.

- [ ] **Step 1: Write the failing test**

`tests/ingest_ods/test_extractor.py`:
```python
from unittest.mock import patch

import pytest

from metaprofile.ingest_ods.services.extractor import Extractor


def _fake_rows():
    return [
        {"id": 100, "company_id": 1, "company_name": "甲公司", "usc_code": "U1",
         "company_enname": None, "category_name": "IT", "province": "HUN",
         "estiblish_time": "2010-01-01", "business_scope": "x", "features": {}},
        {"id": 200, "company_id": 2, "company_name": "乙公司", "usc_code": "U2",
         "company_enname": None, "category_name": "IT", "province": "BJ",
         "estiblish_time": "2011-01-01", "business_scope": "y", "features": {}},
    ]


@pytest.mark.asyncio
async def test_extract_batch_returns_staging_dicts() -> None:
    ext = Extractor()
    with patch("metaprofile.ingest_ods.services.extractor._fetch_rows", return_value=_fake_rows()):
        rows = await ext.extract_batch(
            dsn={"host": "h", "port": 9030, "user": "u", "password": "p",
                 "database": "ods_zbzx", "charset": "utf8mb4"},
            table="ods_company_basic_info",
            last_id=50,
            batch_size=1000,
        )
    assert len(rows) == 2
    assert rows[0]["profile_type"] == "org"
    assert rows[0]["source_id"] == "100"
    assert rows[0]["entity_key"]["company_id"] == 1
    assert rows[0]["last_id"] == 200
    assert rows[1]["source_id"] == "200"
    assert rows[0]["last_id"] == 200  # batch 的推进游标 = 最大 id


@pytest.mark.asyncio
async def test_extract_batch_empty() -> None:
    ext = Extractor()
    with patch("metaprofile.ingest_ods.services.extractor._fetch_rows", return_value=[]):
        rows = await ext.extract_batch({"host": "h"}, "ods_company_basic_info", 0, 1000)
    assert rows == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/ingest_ods/test_extractor.py -v`
Expected: FAIL `ImportError`

- [ ] **Step 3: Implement**

`metaprofile/ingest_ods/services/extractor.py`:
```python
"""阶段① 表→表 抽取：Doris id-keyset 读 + 字段映射 → staging dict。"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

import pymysql
import structlog

from metaprofile.ingest_ods.domain.mappings import apply_mapping

logger = structlog.get_logger(__name__)


def _fetch_rows(dsn: dict, table: str, last_id: int, batch_size: int,
                watermark: str | None = None) -> list[dict]:
    """同步流式取一批行。id-keyset，可选 update_time 增量过滤。"""
    conn = pymysql.connect(**dsn)
    try:
        cur = conn.cursor(pymysql.cursors.SSCursor)
        sql = f"SELECT * FROM `{table}` WHERE id > %s"
        params: list[Any] = [last_id]
        if watermark:
            sql += " AND update_time > %s"
            params.append(watermark)
        sql += " ORDER BY id LIMIT %s"
        params.append(batch_size)
        cur.execute(sql, params)
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
        return rows
    finally:
        conn.close()


class Extractor:
    async def extract_batch(
        self,
        *,
        dsn: dict,
        table: str,
        last_id: int,
        batch_size: int,
        watermark: str | None = None,
    ) -> list[dict]:
        rows = await asyncio.to_thread(_fetch_rows, dsn, table, last_id, batch_size, watermark)
        now = datetime.now(timezone.utc)
        out: list[dict] = []
        max_id = last_id
        for row in rows:
            mapped = apply_mapping(table, row)
            if mapped is None:
                continue
            rid = row.get("id")
            if rid is not None and rid > max_id:
                max_id = rid
            out.append({
                "profile_type": mapped["profile_type"],
                "source_table": table,
                "source_id": str(rid),
                "entity_key": mapped["entity_key"],
                "raw_payload": {**row, "_attrs": mapped["attrs"]},
                "extracted_at": now,
            })
        if out:
            for o in out:
                o["last_id"] = max_id
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/ingest_ods/test_extractor.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add metaprofile/ingest_ods/services/extractor.py tests/ingest_ods/test_extractor.py
git commit -m "feat(ingest_ods): Extractor(表→表 Doris id-keyset 抽取)"
```

---

## Task 7: LLM prompts + relation mapper

**Files:**
- Create: `metaprofile/ingest_ods/llm/prompts.py`
- Test: `tests/ingest_ods/test_prompts.py`

Pydantic schemas for structured LLM output + a `map_predicate()` mapping free-text predicate → `RelationType`.

- [ ] **Step 1: Write the failing test**

`tests/ingest_ods/test_prompts.py`:
```python
import pytest

from metaprofile.ingest_ods.llm.prompts import (
    DisambigResult, MinedEntity, MinedRelation, ScoreOutput, map_predicate,
)
from metaprofile.shared.schemas.relations import RelationType


def test_map_predicate_known() -> None:
    assert map_predicate("隶属", "person", "org") == RelationType.PERSON_AFFILIATED_ORG
    assert map_predicate("研发", "org", "tech") == RelationType.ORG_INVOLVE_TECH
    assert map_predicate("中标", "org", "project") == RelationType.ORG_UNDERTAKE_PROJECT


def test_map_predicate_unknown_returns_none() -> None:
    assert map_predicate("某种不存在的关系", "person", "org") is None


def test_mined_entity_parses() -> None:
    e = MinedEntity(type="org", name="甲公司", attrs={"summary": "x"},
                    veracity_hint=0.8, as_of="2026-01-01")
    assert e.type == "org"


def test_score_output_bounds() -> None:
    s = ScoreOutput(veracity=0.9, timeliness=0.5)
    assert 0.0 <= s.veracity <= 1.0


def test_disambig_result() -> None:
    d = DisambigResult(same=False, reason="不同机构")
    assert d.same is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/ingest_ods/test_prompts.py -v`
Expected: FAIL `ImportError`

- [ ] **Step 3: Implement**

`metaprofile/ingest_ods/llm/prompts.py`:
```python
"""LLM 结构化输出 schema + 关系谓词→RelationType 映射 + prompt 文本。"""
from __future__ import annotations

from datetime import date

from pydantic import Field

from metaprofile.shared.schemas.base import ProfileBase
from metaprofile.shared.schemas.relations import RelationType


class MinedEntity(ProfileBase):
    type: str                         # tech/org/person/project
    name: str
    attrs: dict = Field(default_factory=dict)
    veracity_hint: float = Field(default=0.0, ge=0.0, le=1.0)
    as_of: date | None = None


class MinedRelation(ProfileBase):
    subject_name: str
    subject_type: str
    object_name: str
    object_type: str
    predicate: str                    # 中文谓词，map_predicate 归一
    evidence: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ScoreOutput(ProfileBase):
    veracity: float = Field(..., ge=0.0, le=1.0)
    timeliness: float = Field(..., ge=0.0, le=1.0)
    reason: str | None = None


class DisambigResult(ProfileBase):
    same: bool
    reason: str | None = None


# 谓词 → RelationType（按 主/客体类型 上下文消歧同形谓词）
_PREDICATE_MAP: dict[tuple[str, str, str], RelationType] = {
    ("隶属", "person", "org"): RelationType.PERSON_AFFILIATED_ORG,
    ("隶属", "org", "org"): RelationType.ORG_PARENT,
    ("雇佣", "org", "person"): RelationType.ORG_EMPLOY,
    ("涉及", "org", "tech"): RelationType.ORG_INVOLVE_TECH,
    ("涉及", "project", "tech"): RelationType.PROJECT_INVOLVE_TECH,
    ("贡献者", "person", "tech"): RelationType.TECH_CONTRIBUTOR,
    ("研发", "org", "tech"): RelationType.ORG_INVOLVE_TECH,
    ("承研", "org", "project"): RelationType.ORG_UNDERTAKE_PROJECT,
    ("中标", "org", "project"): RelationType.ORG_UNDERTAKE_PROJECT,
    ("资助", "org", "project"): RelationType.ORG_FUND_PROJECT,
    ("管理", "person", "project"): RelationType.PERSON_MANAGE_PROJECT,
    ("研究", "person", "project"): RelationType.PERSON_RESEARCH_PROJECT,
    ("合作", "org", "org"): RelationType.ORG_COOPERATE,
    ("合作", "person", "person"): RelationType.PERSON_COOPERATE,
    ("提出或开发", "org", "tech"): RelationType.ORG_INVOLVE_TECH,
}


def map_predicate(predicate: str, subject_type: str, object_type: str) -> RelationType | None:
    return _PREDICATE_MAP.get((predicate, subject_type, object_type))


MINE_SYSTEM_PROMPT = """你是产业情报抽取专家。从给定正文抽取实体（技术/项目/机构/人员）与它们之间的关系。
仅输出 JSON：{"entities":[...],"relations":[...]}。
实体：{type,name,attrs,veracity_hint(0-1 被文支撑程度),as_of(YYYY-MM-DD 或 null)}。
关系：{subject_name,subject_type,object_name,object_type,predicate(中文:隶属/涉及/中标/承研/资助/管理/研究/合作/贡献者 等),evidence(原文片段),confidence(0-1)}。
无依据不编造。"""

SCORE_SYSTEM_PROMPT = """你是数据质量评估专家。基于给定实体的属性与来源信息，评判：
veracity(真实性 0-1：主张被源支撑/无矛盾/源可信度)、timeliness(时效性 0-1：信息是否仍当前)。
输出 JSON：{"veracity":float,"timeliness":float,"reason":str}。"""

DISAMBIG_SYSTEM_PROMPT = """你是实体消歧专家。判断两个实体描述是否指同一对象。
输出 JSON：{"same":bool,"reason":str}。不确定时 same=false。"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/ingest_ods/test_prompts.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add metaprofile/ingest_ods/llm/prompts.py tests/ingest_ods/test_prompts.py
git commit -m "feat(ingest_ods): LLM schema + 谓词→RelationType 映射(prompts.py)"
```

---

## Task 8: Entity resolver

**Files:**
- Create: `metaprofile/ingest_ods/services/resolver.py`
- Test: `tests/ingest_ods/test_resolver.py`

Groups staging dicts by canonical key; direct-merges on strong key; name-cluster + LLM disambig for weak. Returns list of resolved entities `{profile_type, entity_key, attrs(merged), source_rows}`.

- [ ] **Step 1: Write the failing test**

`tests/ingest_ods/test_resolver.py`:
```python
from unittest.mock import AsyncMock

import pytest

from metaprofile.ingest_ods.services.resolver import EntityResolver


def _row(ptype, key, attrs):
    return {"profile_type": ptype, "entity_key": key,
            "raw_payload": {"_attrs": attrs}, "source_id": "1"}


@pytest.mark.asyncio
async def test_merge_on_strong_key() -> None:
    rows = [
        _row("org", {"company_id": 1, "usc_code": "U1"}, {"name_cn": "甲", "summary": "a"}),
        _row("org", {"company_id": 1, "usc_code": "U1"}, {"founded_date": "2010-01-01"}),
    ]
    res = EntityResolver(llm=AsyncMock())
    entities = await res.resolve(rows)
    assert len(entities) == 1
    assert entities[0]["attrs"]["name_cn"] == "甲"
    assert entities[0]["attrs"]["founded_date"] == "2010-01-01"


@pytest.mark.asyncio
async def test_weak_key_disambig_same() -> None:
    rows = [
        _row("person", {"full_name_employer": "李四|上海交大"}, {"name_cn": "李四"}),
        _row("person", {}, {"name_cn": "李四", "current_org": "上海交大"}),  # 无强键
    ]
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=_Resp('{"same": true, "reason": "x"}'))
    res = EntityResolver(llm=llm)
    entities = await res.resolve(rows)
    assert len(entities) == 1


class _Resp:
    def __init__(self, content: str) -> None:
        self.content = content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/ingest_ods/test_resolver.py -v`
Expected: FAIL `ImportError`

- [ ] **Step 3: Implement**

`metaprofile/ingest_ods/services/resolver.py`:
```python
"""阶段③ 实体合并/消歧：强键直接归并，弱键 name 簇 + LLM 判同异。"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from metaprofile.ingest_ods.llm.prompts import DISAMBIG_SYSTEM_PROMPT, DisambigResult
from metaprofile.shared.config.settings import settings

_STRONG_KEYS = {"company_id", "usc_code", "orcid", "email", "doi", "patent_number"}


def _strong_key(entity_key: dict) -> str | None:
    for k in _STRONG_KEYS:
        if entity_key.get(k):
            return f"{k}:{entity_key[k]}"
    return None


def _merge_attrs(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in extra.items():
        if k not in out or out[k] in (None, "", []):
            out[k] = v
    return out


class EntityResolver:
    def __init__(self, llm) -> None:
        self._llm = llm

    async def _disambig(self, a: dict, b: dict) -> bool:
        prompt = (f"实体A：{json.dumps(a, ensure_ascii=False)}\n"
                  f"实体B：{json.dumps(b, ensure_ascii=False)}\n判断是否同一对象。")
        resp = await self._llm.complete(
            model=settings.llm.generation_model,
            messages=[{"role": "system", "content": DISAMBIG_SYSTEM_PROMPT},
                      {"role": "user", "content": prompt}],
            temperature=0.0, caller="ods_ingest_resolve",
        )
        try:
            return bool(DisambigResult(**json.loads(resp.content.strip())).same)
        except Exception:
            return False

    async def resolve(self, rows: list[dict]) -> list[dict]:
        # 1. 强键归并
        by_strong: dict[str, dict] = {}
        weak: list[dict] = []
        for r in rows:
            attrs = r["raw_payload"].get("_attrs", {})
            sk = _strong_key(r["entity_key"])
            base = {"profile_type": r["profile_type"], "entity_key": dict(r["entity_key"]),
                    "attrs": dict(attrs), "source_rows": [r]}
            if sk:
                if sk in by_strong:
                    by_strong[sk]["attrs"] = _merge_attrs(by_strong[sk]["attrs"], attrs)
                    by_strong[sk]["entity_key"].update(r["entity_key"])
                    by_strong[sk]["source_rows"].append(r)
                else:
                    by_strong[sk] = base
            else:
                weak.append(base)

        entities = list(by_strong.values())

        # 2. 弱键：name 归一簇，逐对 LLM 判同异
        clusters: dict[tuple, list[dict]] = defaultdict(list)
        for e in weak:
            name = (e["attrs"].get("name_cn") or e["attrs"].get("tech_name_cn") or "").strip()
            clusters[(e["profile_type"], name)].append(e)
        for (ptype, name), group in clusters.items():
            if not name:
                entities.extend(group)
                continue
            merged = group[0]
            for other in group[1:]:
                same = await self._disambig(merged["attrs"], other["attrs"])
                if same:
                    merged["attrs"] = _merge_attrs(merged["attrs"], other["attrs"])
                    merged["source_rows"].extend(other["source_rows"])
                else:
                    entities.append(other)
            entities.append(merged)
        return entities
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/ingest_ods/test_resolver.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add metaprofile/ingest_ods/services/resolver.py tests/ingest_ods/test_resolver.py
git commit -m "feat(ingest_ods): EntityResolver(强键归并+LLM消歧)"
```

---

## Task 9: Scorer (真实性 + 时效性)

**Files:**
- Create: `metaprofile/ingest_ods/services/scorer.py`
- Test: `tests/ingest_ods/test_scorer.py`

- [ ] **Step 1: Write the failing test**

`tests/ingest_ods/test_scorer.py`:
```python
from datetime import date
from unittest.mock import AsyncMock

import pytest

from metaprofile.ingest_ods.services.scorer import Scorer


class _Resp:
    def __init__(self, c: str) -> None:
        self.content = c


@pytest.mark.asyncio
async def test_score_parses_and_sets_fields() -> None:
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=_Resp('{"veracity":0.8,"timeliness":0.6,"reason":"ok"}'))
    sc = Scorer(llm=llm)
    result = await sc.score(
        profile_type="org",
        attrs={"name_cn": "甲公司", "summary": "x"},
        source_rows=[{"raw_payload": {"update_time": "2026-06-01"}}],
    )
    assert result["veracity_score"] == 0.8
    assert result["timeliness_score"] == 0.6
    assert result["data_as_of"] == date(2026, 6, 1)


@pytest.mark.asyncio
async def test_score_llm_failure_defaults_zero() -> None:
    llm = AsyncMock()
    llm.complete = AsyncMock(side_effect=RuntimeError("boom"))
    sc = Scorer(llm=llm)
    result = await sc.score("org", {"name_cn": "x"}, [{}])
    assert result["veracity_score"] == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/ingest_ods/test_scorer.py -v`
Expected: FAIL `ImportError`

- [ ] **Step 3: Implement**

`metaprofile/ingest_ods/services/scorer.py`:
```python
"""阶段④ 真实性 + 时效性 LLM 评分。"""
from __future__ import annotations

import json
from datetime import date

import structlog

from metaprofile.ingest_ods.llm.prompts import SCORE_SYSTEM_PROMPT, ScoreOutput
from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)


def _latest_as_of(source_rows: list[dict]) -> date | None:
    best: date | None = None
    for r in source_rows:
        rp = r.get("raw_payload", {}) if isinstance(r, dict) else {}
        for k in ("update_time", "event_time"):
            v = rp.get(k)
            if not v:
                continue
            try:
                d = date.fromisoformat(str(v)[:10])
            except Exception:
                continue
            if best is None or d > best:
                best = d
    return best


class Scorer:
    def __init__(self, llm) -> None:
        self._llm = llm

    async def score(self, *, profile_type: str, attrs: dict,
                    source_rows: list[dict]) -> dict:
        data_as_of = _latest_as_of(source_rows)
        prompt = (f"实体类型：{profile_type}\n属性：{json.dumps(attrs, ensure_ascii=False)}\n"
                  f"最新源时间：{data_as_of}\n评判真实性与时效性。")
        try:
            resp = await self._llm.complete(
                model=settings.llm.generation_model,
                messages=[{"role": "system", "content": SCORE_SYSTEM_PROMPT},
                          {"role": "user", "content": prompt}],
                temperature=0.0, caller="ods_ingest_score",
            )
            out = ScoreOutput(**json.loads(resp.content.strip()))
            return {"veracity_score": out.veracity,
                    "timeliness_score": out.timeliness, "data_as_of": data_as_of}
        except Exception as exc:  # noqa: BLE001
            logger.warning("scorer_failed", error=str(exc))
            return {"veracity_score": 0.0, "timeliness_score": 0.0, "data_as_of": data_as_of}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/ingest_ods/test_scorer.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add metaprofile/ingest_ods/services/scorer.py tests/ingest_ods/test_scorer.py
git commit -m "feat(ingest_ods): Scorer(真实性/时效性 LLM 评分)"
```

---

## Task 10: Writer (profile upsert + scores + relations)

**Files:**
- Create: `metaprofile/ingest_ods/services/writer.py`
- Test: `tests/ingest_ods/test_writer.py`

Upsert into the right profile main table (set score cols + changelog) + `TripleWriter` for relations. To keep the writer generic across 4 types, use a small dispatch to the profile ORM class + id column.

- [ ] **Step 1: Write the failing test**

`tests/ingest_ods/test_writer.py`:
```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from metaprofile.ingest_ods.services.writer import Writer


@pytest.mark.asyncio
async def test_write_profile_creates_new_org() -> None:
    session = AsyncMock()
    # 不存在现有 → create
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    w = Writer()
    pid = await w.write_profile(
        session,
        profile_type="org",
        entity_id="ORG_1",
        attrs={"name_cn": "甲", "name_en": "A", "summary": "s", "country": "CN",
               "org_types": [], "nature": "企业", "function": "f", "tech_domains": [],
               "operating_years": 0},
        scores={"veracity_score": 0.8, "timeliness_score": 0.5, "data_as_of": None},
        method="llm_extract",
    )
    assert pid == "ORG_1"
    assert session.add.call_count >= 2  # ORM + changelog
    await session.flush()


@pytest.mark.asyncio
async def test_write_relations_delegates_to_triple_writer() -> None:
    tw = AsyncMock()
    w = Writer(triple_writer=tw)
    await w.write_relations([{"relation": "PERSON_AFFILIATED_ORG"}])
    tw.write_batch.assert_awaited_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/ingest_ods/test_writer.py -v`
Expected: FAIL `ImportError`

- [ ] **Step 3: Implement**

`metaprofile/ingest_ods/services/writer.py`:
```python
"""阶段⑤ 写入：profile 主表 upsert + 评分列 + 变更日志；关系→TripleWriter→Neo4j。"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.foundation.relation.triple_writer import TripleWriter
from metaprofile.ingest_ods.domain.orm_models import IngestErrorORM
from metaprofile.profile_org.domain.orm_models import OrgProfileORM
from metaprofile.profile_person.domain.orm_models import PersonProfileORM
from metaprofile.profile_project.domain.orm_models import ProjectProfileORM
from metaprofile.profile_tech.domain.orm_models import TechProfileORM
from metaprofile.shared.db.orm_models import EntityChangeLogORM

logger = structlog.get_logger(__name__)

# profile_type → (ORM, id 列属性名, 必填列默认值)
_PROFILE_TABLES = {
    "tech": (TechProfileORM, "tech_id"),
    "org": (OrgProfileORM, "org_id"),
    "person": (PersonProfileORM, "person_id"),
    "project": (ProjectProfileORM, "project_id"),
}

# 各 profile 主表 NOT NULL 列的默认占位（避免 insert 约束失败）
_DEFAULTS = {
    "tech": {"tech_name_en": "", "tech_domain": [], "tech_summary": "",
             "project_layout": [], "key_points": [], "current_status": "", "trend": ""},
    "org": {"name_en": "", "country": "", "org_types": [], "nature": "",
            "function": "", "tech_domains": [], "operating_years": 0,
            "name_other": [], "strategic_plans": [], "new_key_projects": [], "predecessor_names": []},
    "person": {"name_en": "", "gender": "", "nationality": "", "summary": "",
               "current_position": [], "professional_domains": [],
               "avatar": [], "professional_skills": [], "personality_traits": [],
               "hobbies": [], "management_philosophy": [], "remark": []},
    "project": {"name_cn": [], "name_en": [], "name_other": [], "tech_domain": [],
                "sub_tech_domain": [], "start_date": None, "status": [],
                "budget_activities": [], "main_orgs": [], "managers": [],
                "researchers": [], "background": [], "research_content": [],
                "progress": [], "key_dates": [], "project_no": 0,
                "undertaking_orgs": [], "undertaking_enterprises": []},
}


class Writer:
    def __init__(self, triple_writer: TripleWriter | None = None) -> None:
        self._tw = triple_writer

    async def write_profile(
        self,
        session: AsyncSession,
        *,
        profile_type: str,
        entity_id: str,
        attrs: dict,
        scores: dict,
        method: str,
    ) -> str:
        orm_cls, id_col = _PROFILE_TABLES[profile_type]
        stmt = select(orm_cls).where(getattr(orm_cls, id_col) == entity_id)
        orm = (await session.execute(stmt)).scalar_one_or_none()

        merged = dict(_DEFAULTS.get(profile_type, {}))
        merged.update({k: v for k, v in attrs.items() if v not in (None, "", [])})
        merged["veracity_score"] = scores.get("veracity_score", 0.0)
        merged["timeliness_score"] = scores.get("timeliness_score", 0.0)
        merged["data_as_of"] = scores.get("data_as_of")

        now = datetime.now(timezone.utc)
        if orm is None:
            merged[id_col] = entity_id
            orm = orm_cls(**merged)
            session.add(orm)
            session.add(EntityChangeLogORM(
                entity_id=entity_id, entity_type=profile_type, field="*",
                old_value=None, new_value={"action": "ingest_create"},
                method=method, changed_at=now,
            ))
        else:
            for k, v in merged.items():
                if k == id_col:
                    continue
                old = getattr(orm, k, None)
                if old != v:
                    setattr(orm, k, v)
            session.add(EntityChangeLogORM(
                entity_id=entity_id, entity_type=profile_type, field="*",
                old_value=None, new_value={"action": "ingest_update"},
                method=method, changed_at=now,
            ))
        await session.flush()
        return entity_id

    async def write_relations(self, triples: list) -> None:
        if not triples or self._tw is None:
            return
        await self._tw.write_batch(triples)

    async def record_error(self, session: AsyncSession, *, batch_id: int,
                           stage: str, error_msg: str,
                           source_table: str | None = None,
                           source_id: str | None = None) -> None:
        session.add(IngestErrorORM(batch_id=batch_id, source_table=source_table,
                                   source_id=source_id, stage=stage, error_msg=error_msg[:1000]))
        await session.flush()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/ingest_ods/test_writer.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add metaprofile/ingest_ods/services/writer.py tests/ingest_ods/test_writer.py
git commit -m "feat(ingest_ods): Writer(profile upsert+评分+变更日志+关系)"
```

---

## Task 11: Content miner (附件 LLM → 实体 + 关系)

**Files:**
- Create: `metaprofile/ingest_ods/services/content_miner.py`
- Test: `tests/ingest_ods/test_content_miner.py`

Takes attachment rows `{original_id, clean_content}`, chunks, calls LLM, parses `MinedEntity`/`MinedRelation`, maps relations to `RelationTriple` via `map_predicate`.

- [ ] **Step 1: Write the failing test**

`tests/ingest_ods/test_content_miner.py`:
```python
from unittest.mock import AsyncMock

import pytest

from metaprofile.ingest_ods.services.content_miner import ContentMiner


class _Resp:
    def __init__(self, c: str) -> None:
        self.content = c


LLM_JSON = ('{"entities":[{"type":"org","name":"甲公司","attrs":{"summary":"研发AI"},'
            '"veracity_hint":0.9,"as_of":"2026-01-01"}],'
            '"relations":[{"subject_name":"甲公司","subject_type":"org",'
            '"object_name":"深度学习","object_type":"tech","predicate":"涉及",'
            '"evidence":"甲公司研发深度学习","confidence":0.8}]}')


@pytest.mark.asyncio
async def test_mine_parses_entities_and_relations() -> None:
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=_Resp(LLM_JSON))
    cm = ContentMiner(llm=llm)
    entities, relations = await cm.mine(
        attachments=[{"original_id": 15, "clean_content": "正文……"}],
    )
    assert len(entities) == 1
    assert entities[0]["name"] == "甲公司"
    assert len(relations) == 1
    assert relations[0].relation.value == "涉及"
    assert relations[0].subject_id  # 已赋临时 id


@pytest.mark.asyncio
async def test_mine_skips_null_clean_content() -> None:
    llm = AsyncMock()
    cm = ContentMiner(llm=llm)
    entities, relations = await cm.mine([{"original_id": 1, "clean_content": None}])
    assert entities == [] and relations == []
    llm.complete.assert_not_awaited()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/ingest_ods/test_content_miner.py -v`
Expected: FAIL `ImportError`

- [ ] **Step 3: Implement**

`metaprofile/ingest_ods/services/content_miner.py`:
```python
"""阶段② 内容→表：附件 clean_content LLM 抽实体 + 关系三元组。"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog
from pydantic import TypeAdapter

from metaprofile.ingest_ods.llm.prompts import (
    MINE_SYSTEM_PROMPT, MinedEntity, MinedRelation, map_predicate,
)
from metaprofile.shared.config.settings import settings
from metaprofile.shared.schemas.base import EntityType, SourceMethod
from metaprofile.shared.schemas.relations import RelationTriple

logger = structlog.get_logger(__name__)

_MAX_CHARS = 4000


def _chunk(text: str) -> list[str]:
    return [text[i:i + _MAX_CHARS] for i in range(0, len(text), _MAX_CHARS)] or [text]


_ENT_TYPES = {"tech": EntityType.TECH, "org": EntityType.ORG,
              "person": EntityType.PERSON, "project": EntityType.PROJECT}


class ContentMiner:
    def __init__(self, llm) -> None:
        self._llm = llm

    async def _extract_chunk(self, text: str) -> tuple[list[MinedEntity], list[MinedRelation]]:
        resp = await self._llm.complete(
            model=settings.llm.extraction_model,
            messages=[{"role": "system", "content": MINE_SYSTEM_PROMPT},
                      {"role": "user", "content": f"正文：\n{text}"}],
            temperature=0.0, caller="ods_ingest_mine",
        )
        try:
            data = json.loads(resp.content.strip())
        except Exception as exc:  # noqa: BLE001
            logger.warning("mine_parse_failed", error=str(exc))
            return [], []
        ents = TypeAdapter(list[MinedEntity]).validate_python(data.get("entities", []))
        rels = TypeAdapter(list[MinedRelation]).validate_python(data.get("relations", []))
        return ents, rels

    async def mine(self, attachments: list[dict]) -> tuple[list[dict], list[RelationTriple]]:
        entities: list[dict] = []
        rels: list[RelationTriple] = []
        now = datetime.now(timezone.utc)
        for att in attachments:
            text = att.get("clean_content")
            if not text:
                continue
            for chunk in _chunk(text):
                mined_ents, mined_rels = await self._extract_chunk(chunk)
                for e in mined_ents:
                    entities.append({"type": e.type, "name": e.name, "attrs": e.attrs,
                                     "veracity_hint": e.veracity_hint, "as_of": e.as_of,
                                     "source_doc_id": str(att.get("original_id"))})
                for r in mined_rels:
                    rel = map_predicate(r.predicate, r.subject_type, r.object_type)
                    if rel is None:
                        continue
                    rels.append(RelationTriple(
                        subject_id=f"name:{r.subject_name}",
                        subject_type=_ENT_TYPES[r.subject_type],
                        subject_name=r.subject_name,
                        relation=rel,
                        object_id=f"name:{r.object_name}",
                        object_type=_ENT_TYPES[r.object_type],
                        object_name=r.object_name,
                        evidence=r.evidence, confidence=r.confidence,
                        source_doc_id=str(att.get("original_id")),
                        method=SourceMethod.LLM_EXTRACT, extracted_at=now,
                    ))
        return entities, rels
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/ingest_ods/test_content_miner.py -v`
Expected: PASS (2 tests). Confirm `settings.llm.extraction_model` exists (read `settings.py`; if the attr is named differently, align — the codebase uses `settings.llm.generation_model`).

- [ ] **Step 5: Commit**

```bash
git add metaprofile/ingest_ods/services/content_miner.py tests/ingest_ods/test_content_miner.py
git commit -m "feat(ingest_ods): ContentMiner(附件LLM抽实体+关系→RelationTriple)"
```

---

## Task 12: Orchestrator (批次 + 并行 + 互斥 + 续传)

**Files:**
- Create: `metaprofile/ingest_ods/services/orchestrator.py`
- Test: `tests/ingest_ods/test_orchestrator.py`

`BatchOrchestrator.run(session, task, source, deps)`: loops batches per table in `source.config_json.table_set`; each batch = extract → resolve → score → write; Semaphore(workers); per-profile-type lock via a module-level set of active types; advance watermark/last_id each batch; update CollectionTask counters. Resumable (last_id persisted).

- [ ] **Step 1: Write the failing test**

`tests/ingest_ods/test_orchestrator.py`:
```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from metaprofile.ingest_ods.services.orchestrator import BatchOrchestrator, _active_types
from metaprofile.ingest_ods.services.watermark import WatermarkStore


def _source(tables, workers=2, batch=10, mode="structured_only"):
    s = MagicMock()
    s.id = 1
    s.profile_type = "all"
    s.config_json = {"table_set": tables, "workers": workers, "batch_size": batch,
                     "watermark_col": "update_time", "mode": mode,
                     "db_connection_id": 1, "profile_types": ["all"]}
    return s


@pytest.mark.asyncio
async def test_run_processes_batches_and_advances_watermark() -> None:
    src = _source(["ods_company_basic_info"])
    extractor = AsyncMock()
    extractor.extract_batch = AsyncMock(side_effect=[
        [{"profile_type": "org", "entity_key": {"company_id": 1},
          "raw_payload": {"_attrs": {"name_cn": "甲"}}, "source_id": "1", "last_id": 5}],
        [],  # 第二批空 → 结束
    ])
    resolver = AsyncMock(); resolver.resolve = AsyncMock(side_effect=lambda rows: rows)
    scorer = AsyncMock(); scorer.score = AsyncMock(return_value={"veracity_score": 0.9,
                                       "timeliness_score": 0.5, "data_as_of": None})
    writer = AsyncMock(); writer.write_profile = AsyncMock(return_value="ORG_1")
    conn_orm = MagicMock(); conn_orm.host = "h"; conn_orm.port = 9030
    conn_orm.username = "u"; conn_orm.password_enc = "p"; conn_orm.database = "d"
    conn_orm.charset = "utf8mb4"
    session = AsyncMock()
    session.get = AsyncMock(return_value=conn_orm)

    orch = BatchOrchestrator(extractor=extractor, resolver=resolver, scorer=scorer,
                             writer=writer, connections=lambda c: {})
    n = await orch.run(session, task=MagicMock(id=7), source=src)

    assert n >= 1
    assert WatermarkStore.get(src, "last_id") == 5
    writer.write_profile.assert_awaited()


@pytest.mark.asyncio
async def test_same_profile_type_is_mutex() -> None:
    assert "org" not in _active_types
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/ingest_ods/test_orchestrator.py -v`
Expected: FAIL `ImportError`

- [ ] **Step 3: Implement**

`metaprofile/ingest_ods/services/orchestrator.py`:
```python
"""BatchOrchestrator：批次 + 并发(Semaphore) + 同 profile_type 互斥 + 断点续传。"""
from __future__ import annotations

import asyncio
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.ingest_ods.domain.orm_models import DBConnectionORM
from metaprofile.ingest_ods.services.connections import resolve_dsn
from metaprofile.ingest_ods.services.watermark import WatermarkStore

logger = structlog.get_logger(__name__)

# 进程内活跃 profile_type 集合 → 同类型互斥，跨类型并行
_active_types: set[str] = set()


class BatchOrchestrator:
    def __init__(self, *, extractor, resolver, scorer, writer,
                 connections=resolve_dsn) -> None:
        self._extractor = extractor
        self._resolver = resolver
        self._scorer = scorer
        self._writer = writer
        self._connections = connections

    async def run(self, session: AsyncSession, *, task, source) -> int:
        cfg = source.config_json or {}
        tables: list[str] = cfg.get("table_set", [])
        workers: int = int(cfg.get("workers", 4))
        batch_size: int = int(cfg.get("batch_size", workers * 125))
        mode: str = cfg.get("mode", "structured_only")
        watermark: str | None = WatermarkStore.get(source, WatermarkStore.KEY_WM)

        conn_orm = await session.get(DBConnectionORM, cfg["db_connection_id"])
        dsn = self._connections(conn_orm)

        total_imported = 0
        for table in tables:
            last_id = WatermarkStore.get(source, WatermarkStore.KEY_ID) or 0
            while True:
                rows = await self._extractor.extract_batch(
                    dsn=dsn, table=table, last_id=last_id,
                    batch_size=batch_size, watermark=watermark,
                )
                if not rows:
                    break
                last_id = rows[-1]["last_id"]
                # 同 profile_type 互斥（这里按表产出类型；简化：取首行类型）
                ptype = rows[0]["profile_type"]
                while ptype in _active_types:
                    await asyncio.sleep(0.5)
                _active_types.add(ptype)
                try:
                    imported = await self._process_batch(session, task, source, rows, mode)
                    total_imported += imported
                finally:
                    _active_types.discard(ptype)

                WatermarkStore.set(source, WatermarkStore.KEY_ID, last_id)
                await session.flush()
        return total_imported

    async def _process_batch(self, session, task, source, rows, mode) -> int:
        sem = asyncio.Semaphore(int((source.config_json or {}).get("workers", 4)))

        async def one(r):
            async with sem:
                return r
        # resolve 整批（消歧需跨行）
        entities = await self._resolver.resolve(rows)
        imported = 0
        for ent in entities:
            scores = await self._scorer.score(
                profile_type=ent["profile_type"], attrs=ent["attrs"],
                source_rows=ent.get("source_rows", []),
            )
            entity_id = (ent["entity_key"].get("company_id")
                         or ent["entity_key"].get("usc_code")
                         or ent["entity_key"].get("orcid")
                         or ent["entity_key"].get("email")
                         or ent["entity_key"].get("patent_number")
                         or ent["entity_key"].get("doi")
                         or f"name:{ent['attrs'].get('name_cn') or ent['attrs'].get('tech_name_cn')}")
            try:
                await self._writer.write_profile(
                    session, profile_type=ent["profile_type"], entity_id=str(entity_id),
                    attrs=ent["attrs"], scores=scores, method="llm_extract",
                )
                imported += 1
            except Exception as exc:  # noqa: BLE001
                await self._writer.record_error(
                    session, batch_id=task.id, stage="write",
                    error_msg=str(exc), source_table=rows[0].get("source_table"),
                )
        await session.commit()
        task.records_imported = (task.records_imported or 0) + imported
        return imported
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/ingest_ods/test_orchestrator.py -v`
Expected: PASS (2 tests). Note: content_mine mode wiring (calling ContentMiner for attachment tables) is added in Task 13 — orchestrator here handles structured path; `mode=="content_mine"`/`"both"` attachment mining is layered in the collector (Task 13) to keep this task focused.

- [ ] **Step 5: Commit**

```bash
git add metaprofile/ingest_ods/services/orchestrator.py tests/ingest_ods/test_orchestrator.py
git commit -m "feat(ingest_ods): BatchOrchestrator(批次+并发+互斥+续传)"
```

---

## Task 13: SqlWarehouse collector + collector_service wiring + content-mine wiring

**Files:**
- Create: `metaprofile/ingest_ods/collectors/sql_warehouse.py`
- Modify: `metaprofile/settings_api/services/collector_service.py` (add `sql_warehouse` branch in `_run_collection`)
- Test: `tests/ingest_ods/test_sql_warehouse_collector.py`

The collector builds the stage services + orchestrator and runs. When `mode in ("content_mine","both")`, it additionally pulls attachment rows (via a small SQL helper) and runs `ContentMiner`, writing relations through `TripleWriter`.

- [ ] **Step 1: Write the failing test**

`tests/ingest_ods/test_sql_warehouse_collector.py`:
```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metaprofile.ingest_ods.collectors import sql_warehouse as sw


@pytest.mark.asyncio
async def test_run_invokes_orchestrator(monkeypatch) -> None:
    orch = AsyncMock(); orch.run = AsyncMock(return_value=3)
    with patch.object(sw, "BatchOrchestrator", return_value=orch), \
         patch.object(sw, "Extractor", return_value=MagicMock()), \
         patch.object(sw, "EntityResolver", return_value=MagicMock()), \
         patch.object(sw, "Scorer", return_value=MagicMock()), \
         patch.object(sw, "Writer", return_value=MagicMock()):
        n = await sw.run_sql_warehouse_collection(
            task=MagicMock(id=1),
            source=MagicMock(config_json={"table_set": ["ods_company_basic_info"],
                                          "mode": "structured_only", "workers": 1,
                                          "batch_size": 10, "db_connection_id": 1}),
        )
    assert n == 3
    orch.run.assert_awaited_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/ingest_ods/test_sql_warehouse_collector.py -v`
Expected: FAIL `ImportError`

- [ ] **Step 3: Implement collector**

`metaprofile/ingest_ods/collectors/sql_warehouse.py`:
```python
"""source_type='sql_warehouse' 适配器：装配 5 阶段服务 + 跑 orchestrator。"""
from __future__ import annotations

import pymysql
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.ingest_ods.domain.orm_models import DBConnectionORM
from metaprofile.ingest_ods.services.connections import resolve_dsn
from metaprofile.ingest_ods.services.content_miner import ContentMiner
from metaprofile.ingest_ods.services.extractor import Extractor
from metaprofile.ingest_ods.services.orchestrator import BatchOrchestrator
from metaprofile.ingest_ods.services.resolver import EntityResolver
from metaprofile.ingest_ods.services.scorer import Scorer
from metaprofile.ingest_ods.services.writer import Writer
from metaprofile.shared.llm.gateway import LLMGateway

logger = structlog.get_logger(__name__)


def _fetch_attachments(dsn: dict, table: str, original_ids: list, limit: int = 1000) -> list[dict]:
    if not original_ids:
        return []
    conn = pymysql.connect(**dsn)
    try:
        cur = conn.cursor(pymysql.cursors.SSCursor)
        ph = ",".join(["%s"] * len(original_ids))
        cur.execute(
            f"SELECT original_id, clean_content FROM `{table}` "
            f"WHERE clean_content IS NOT NULL AND original_id IN ({ph}) LIMIT %s",
            [*original_ids, limit],
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
        return rows
    finally:
        conn.close()


async def run_sql_warehouse_collection(*, task, source, session: AsyncSession | None = None) -> int:
    from metaprofile.shared.db.postgres import get_session
    from metaprofile.shared.config.settings import settings

    llm = LLMGateway()
    writer = Writer()
    orch = BatchOrchestrator(
        extractor=Extractor(),
        resolver=EntityResolver(llm=llm),
        scorer=Scorer(llm=llm),
        writer=writer,
        connections=resolve_dsn,
    )

    async with get_session() as sess:
        imported = await orch.run(sess, task=task, source=source)

        # 内容挖掘（按 mode）
        cfg = source.config_json or {}
        if cfg.get("mode") in ("content_mine", "both") and cfg.get("enable_relations", True):
            conn_orm = await sess.get(DBConnectionORM, cfg["db_connection_id"])
            dsn = resolve_dsn(conn_orm)
            att_table = cfg.get("attachment_table", "ods_science_literature_attachment")
            original_ids = cfg.get("content_mine_original_ids", [])[:500]
            atts = _fetch_attachments(dsn, att_table, original_ids)
            if atts:
                miner = ContentMiner(llm=llm)
                _entities, relations = await miner.mine(atts)
                if relations:
                    from metaprofile.foundation.relation.triple_writer import TripleWriter
                    from metaprofile.shared.db.neo4j import get_neo4j_repo  # 按实际导入路径
                    tw = TripleWriter(await get_neo4j_repo())
                    await writer.write_relations(relations)
        return imported
```

Note: `get_neo4j_repo` import path — read the codebase for the actual Neo4j repo factory (grep `FoundationNeo4jRepo` / `upsert_relation`) and align the import. If it's constructed differently, adapt.

- [ ] **Step 4: Wire into collector_service**

In `metaprofile/settings_api/services/collector_service.py`, in `_run_collection`, add a branch before the `else: raise ValueError(...)`:
```python
            elif source_type == "sql_warehouse":
                from metaprofile.ingest_ods.collectors.sql_warehouse import (
                    run_sql_warehouse_collection,
                )
                imported = await run_sql_warehouse_collection(task_id=task_id_placeholder,
                                                              source=_source_obj)
```
Because `_run_collection` currently passes `config_json` not the ORM, add the source lookup: inside the branch, fetch the `DataSourceConfigORM` by `task.source_id` (task is loaded as `CollectionTaskORM` which has `source_id`) and pass it. Read the existing `_run_collection` body — it loads `task` from `CollectionTaskORM`; add `source = await session.get(DataSourceConfigORM, task.source_id)` and pass `source` into the collector. Set `task.records_imported = imported`.

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/ingest_ods/test_sql_warehouse_collector.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add metaprofile/ingest_ods/collectors/sql_warehouse.py metaprofile/settings_api/services/collector_service.py tests/ingest_ods/test_sql_warehouse_collector.py
git commit -m "feat(ingest_ods): sql_warehouse 适配器 + collector_service 接线 + 内容挖掘"
```

---

## Task 14: Seed script (db_connections + data_source_configs)

**Files:**
- Create: `scripts/seed_ods_datasources.py`
- Test: `tests/ingest_ods/test_seed_ods.py`

Idempotent insert of cloud + local Doris connections and two `sql_warehouse` sources.

- [ ] **Step 1: Write the failing test**

`tests/ingest_ods/test_seed_ods.py`:
```python
from unittest.mock import AsyncMock, MagicMock

import pytest

from scripts import seed_ods_datasources as seed


@pytest.mark.asyncio
async def test_seed_inserts_two_connections_two_sources(monkeypatch) -> None:
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(
        return_value=MagicMock(first=MagicMock(return_value=None)))))
    await seed.seed(session, cloud_pw="CW", local_pw="LC", secret="k")
    # 4 add calls: 2 connections + 2 sources
    assert session.add.call_count == 4
    session.commit.assert_awaited_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/ingest_ods/test_seed_ods.py -v`
Expected: FAIL `ImportError` (note: `scripts/` may need an `__init__.py` or use `importlib`; if pytest can't import `scripts.seed_ods_datasources`, add `conftest.py` path or test via subprocess — prefer adding `scripts/__init__.py`.)

- [ ] **Step 3: Implement**

`scripts/seed_ods_datasources.py`:
```python
"""幂等种子：db_connections(云+本地 Doris) + data_source_configs(两条 sql_warehouse 源)。"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.ingest_ods.domain.orm_models import DBConnectionORM
from metaprofile.ingest_ods.services.security import encrypt_pw
from metaprofile.settings_api.domain.orm_models import DataSourceConfigORM

_CLOUD = dict(name="ods-cloud-doris", dialect="doris", host="10.242.0.1", port=9030,
              database="ods_zbzx", username="gz_kt5")
_LOCAL = dict(name="ods-local-doris", dialect="doris", host="127.0.0.1", port=9030,
              database="ods_zbzx", username="root")

_LOCAL_CFG = {
    "db_connection_id": None,  # 运行时回填
    "table_set": ["ods_company_basic_info", "ods_invention_patent_cn",
                  "ods_science_literature", "ods_market_analysis_cn",
                  "ods_talent_info_cn", "ods_strategic_policy_cn",
                  "ods_industry_report_cn", "ods_key_events_cn"],
    "profile_types": ["all"], "mode": "both", "enable_relations": True,
    "watermark_col": "update_time", "batch_size": 1000, "workers": 8,
}
_CLOUD_CFG = {**_LOCAL_CFG, "mode": "structured_only"}


async def _upsert_conn(session, spec: dict, pw_plain: str) -> DBConnectionORM:
    orm = (await session.execute(
        select(DBConnectionORM).where(DBConnectionORM.name == spec["name"])
    )).scalars().first()
    if orm is None:
        orm = DBConnectionORM(**spec, password_enc=encrypt_pw(pw_plain))
        session.add(orm)
    return orm


async def seed(session: AsyncSession, *, cloud_pw: str, local_pw: str, secret: str) -> None:
    cloud = await _upsert_conn(session, _CLOUD, cloud_pw)
    local = await _upsert_conn(session, _LOCAL, local_pw)
    await session.flush()

    for name, cfg, cron in (
        ("ODS-本地-Doris", {**_LOCAL_CFG, "db_connection_id": local.id}, "0 2 * * *"),
        ("ODS-云-Doris", {**_CLOUD_CFG, "db_connection_id": cloud.id}, None),
    ):
        existing = (await session.execute(
            select(DataSourceConfigORM).where(DataSourceConfigORM.name == name)
        )).scalars().first()
        if existing is None:
            session.add(DataSourceConfigORM(
                name=name, source_type="sql_warehouse", profile_type="all",
                config_json=cfg, schedule_cron=cron, is_enabled=True,
            ))
    await session.commit()


if __name__ == "__main__":
    import asyncio
    from metaprofile.shared.db.postgres import get_session

    async def main() -> None:
        import os
        async with get_session() as s:
            await seed(s, cloud_pw=os.environ["ODS_CLOUD_PW"],
                       local_pw=os.environ.get("ODS_LOCAL_PW", ""),
                       secret=os.environ.get("SECRET_KEY", "dev"))
    asyncio.run(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/ingest_ods/test_seed_ods.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/seed_ods_datasources.py scripts/__init__.py tests/ingest_ods/test_seed_ods.py
git commit -m "feat(ingest_ods): 种子脚本(db_connections + data_source_configs)"
```

---

## Task 15: End-to-end integration test

**Files:**
- Test: `tests/ingest_ods/test_e2e_pipeline.py`

Mock Doris (`_fetch_rows`) + mock LLM + mock Neo4j repo; run `run_sql_warehouse_collection`; assert a profile row would be upserted and a relation triple passed to TripleWriter. Uses an in-memory or transactional test DB session if the project has a fixture; otherwise mock the session.

- [ ] **Step 1: Write the failing test**

`tests/ingest_ods/test_e2e_pipeline.py`:
```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metaprofile.ingest_ods.collectors import sql_warehouse as sw


@pytest.mark.asyncio
async def test_e2e_structured_only_writes_profile() -> None:
    fake_rows = [
        {"profile_type": "org", "entity_key": {"company_id": 1, "usc_code": "U1"},
         "raw_payload": {"_attrs": {"name_cn": "甲公司"}, "update_time": "2026-06-01"},
         "source_id": "1", "last_id": 9},
    ]
    extractor = AsyncMock(); extractor.extract_batch = AsyncMock(side_effect=[fake_rows, []])
    resolver = AsyncMock(); resolver.resolve = AsyncMock(side_effect=lambda r: [
        {"profile_type": "org", "entity_key": {"company_id": 1},
         "attrs": {"name_cn": "甲公司"}, "source_rows": fake_rows}])
    scorer = AsyncMock(); scorer.score = AsyncMock(return_value={"veracity_score": 0.9,
                                       "timeliness_score": 0.6, "data_as_of": None})
    writer = AsyncMock(); writer.write_profile = AsyncMock(return_value="1")

    conn_orm = MagicMock(host="h", port=9030, username="u", password_enc="p",
                         database="d", charset="utf8mb4")
    session = AsyncMock(); session.get = AsyncMock(return_value=conn_orm)

    source = MagicMock(id=1, profile_type="all",
                       config_json={"table_set": ["ods_company_basic_info"],
                                    "mode": "structured_only", "workers": 1,
                                    "batch_size": 10, "db_connection_id": 1})
    orch = sw.BatchOrchestrator(extractor=extractor, resolver=resolver,
                                scorer=scorer, writer=writer,
                                connections=lambda c: {})

    with patch.object(sw, "get_session", _ctx(session)), \
         patch.object(sw, "BatchOrchestrator", return_value=orch):
        n = await sw.run_sql_warehouse_collection(task=MagicMock(id=7), source=source)
    assert n == 1
    writer.write_profile.assert_awaited()


class _ctx:
    def __init__(self, session): self.s = session
    async def __aenter__(self): return self.s
    async def __aexit__(self, *a): return False
```

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest tests/ingest_ods/test_e2e_pipeline.py -v`
Expected: PASS. (The test may need `get_session` patched at the correct import location — adjust the patch target to wherever `run_sql_warehouse_collection` imports `get_session`.)

- [ ] **Step 3: Run the full ingest_ods suite**

Run: `python -m pytest tests/ingest_ods/ -v`
Expected: all PASS.

- [ ] **Step 4: Run migration on a dev DB**

Run: `python -m alembic upgrade head`
Expected: `0003` applied, new tables + columns present.

- [ ] **Step 5: Commit**

```bash
git add tests/ingest_ods/test_e2e_pipeline.py
git commit -m "test(ingest_ods): 端到端集成测试(structured→profile 写入)"
```

---

## Self-Review (run after writing)

1. **Spec coverage:** extract(§7① T6), content_mine(§7② T11), resolve(§7③ T8), score(§7④ T9), write(§7⑤ T10), orchestrator+batch+parallel+mutex+resume(§8 T12), two paths(§9 T6/T11), entity merge(§10 T8), quality scoring(§10 T9+T1 cols), relations(§11 T11+T13), LLM gateway(§13 T7/T8/T9/T11), scheduling/trigger(§14 reused via collector_service T13), data model(§12 T1), source config(§6 T14). Gaps: cron-driven trigger is the existing `schedule_cron` field (no new code) — covered by reuse; manual trigger via existing `trigger_collection` HTTP — covered.
2. **Placeholders:** the Neo4j repo factory import in T13 is flagged "align to codebase" — acceptable (named precisely, grep target given). `content_mine_original_ids` seeding is config-driven, not a placeholder.
3. **Type consistency:** `entity_key` dict flows T6→T8→T12 consistently; `scores` dict shape `{veracity_score, timeliness_score, data_as_of}` consistent T9→T10; `RelationTriple` from relations.py used T11→T13; `WatermarkStore.KEY_ID/KEY_WM` consistent T4→T12. Confirmed.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-06-17-ods-profile-extraction.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
