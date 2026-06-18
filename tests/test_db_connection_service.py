"""单元测试：DbConnectionService —— db_connections CRUD + 密码加密/脱敏。"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from metaprofile.ingest_ods.services.security import decrypt_pw
from metaprofile.settings_api.schemas.models import (
    DbConnectionCreate,
    DbConnectionOut,
    DbConnectionUpdate,
)
from metaprofile.settings_api.services.db_connection_service import DbConnectionService


def _mock_db(get_return=None) -> AsyncMock:
    db = AsyncMock()
    db.add = MagicMock()
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock(return_value=get_return)
    return db


@pytest.mark.asyncio
async def test_create_encrypts_password():
    svc = DbConnectionService()
    db = _mock_db()
    orm = await svc.create(db, DbConnectionCreate(
        name="ods-local", host="localhost", port=9030,
        database="ods_zbzx", username="root", password="s3cret",
    ))
    assert orm.password_enc != "s3cret"
    assert decrypt_pw(orm.password_enc) == "s3cret"
    assert orm.name == "ods-local"
    assert orm.dialect == "doris"
    db.add.assert_called_once()


@pytest.mark.asyncio
async def test_update_reencrypts_when_password_given():
    svc = DbConnectionService()
    existing = MagicMock()
    existing.password_enc = "old-enc"
    db = _mock_db(get_return=existing)

    await svc.update(db, 1, DbConnectionUpdate(password="newpw", host="newhost"))
    assert existing.password_enc != "old-enc"
    assert decrypt_pw(existing.password_enc) == "newpw"
    assert existing.host == "newhost"


@pytest.mark.asyncio
async def test_update_keeps_password_when_omitted():
    svc = DbConnectionService()
    existing = MagicMock()
    existing.password_enc = "keep-enc"
    db = _mock_db(get_return=existing)

    await svc.update(db, 1, DbConnectionUpdate(host="newhost"))
    assert existing.password_enc == "keep-enc"
    assert existing.host == "newhost"


@pytest.mark.asyncio
async def test_update_returns_none_when_missing():
    svc = DbConnectionService()
    db = _mock_db(get_return=None)
    assert await svc.update(db, 999, DbConnectionUpdate(host="x")) is None


@pytest.mark.asyncio
async def test_delete_returns_true_false():
    svc = DbConnectionService()
    existing = MagicMock()
    assert await svc.delete(_mock_db(get_return=existing), 1) is True
    assert await svc.delete(_mock_db(get_return=None), 999) is False


def test_out_schema_excludes_password():
    fields = DbConnectionOut.model_fields
    assert "password_enc" not in fields
    assert "password" not in fields
    assert "host" in fields
