from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metaprofile.new_tech_discovery.services.corpus_loader import CorpusLoader

_MOD = "metaprofile.new_tech_discovery.services.corpus_loader"
_P_GET_SESSION = f"{_MOD}.get_session"
_P_RESOLVE_DSN = f"{_MOD}.resolve_dsn"
_P_PYMYSQL = f"{_MOD}.pymysql.connect"


def _fake_conn():
    """返回一个 mock pymysql 连接：cur.execute/cur.fetchall/cur.description 可控。"""
    conn = MagicMock()
    cur = MagicMock()
    cur.description = [("id",), ("title",), ("abstract",), ("keyword",), ("pubdate",)]
    cur.fetchall.return_value = [
        (1, "quantum computing", "abstract about qubits", "quantum; qubit", date(2026, 1, 15)),
        (2, "machine learning", "ml abstract", "ml; neural", date(2026, 2, 20)),
    ]
    conn.cursor.return_value = cur
    return conn, cur


def _patch_db_resolver(dsn=None):
    """patch get_session + resolve_dsn，使 load() 不触真实 Postgres / 不走 decrypt_pw。

    get_session → 返回 mock async ctx，其 __aenter__ 返回一个 mock session；
    session.get(DBConnectionORM, id) → 返回 mock ORM（resolve_dsn 被整体 patch，
    不读取 ORM 任何字段，故 mock 即可）。
    resolve_dsn → 返回给定的 dsn（默认一个最小的合法 pymysql 参数 dict）。
    """
    dsn = dsn or {"host": "x", "port": 1, "user": "u", "password": "p", "database": "d"}

    fake_session = MagicMock()
    fake_session.get = AsyncMock(return_value=MagicMock(name="fake_orm"))

    fake_ctx = MagicMock()
    fake_ctx.__aenter__ = AsyncMock(return_value=fake_session)
    fake_ctx.__aexit__ = AsyncMock(return_value=False)

    return (
        patch(_P_GET_SESSION, return_value=fake_ctx),
        patch(_P_RESOLVE_DSN, return_value=dsn),
    )


@pytest.mark.asyncio
async def test_load_science_maps_to_corpus_doc():
    conn, _ = _fake_conn()
    p_sess, p_dsn = _patch_db_resolver()
    with p_sess, p_dsn, patch(_P_PYMYSQL, return_value=conn):
        loader = CorpusLoader()
        docs = await loader.load(
            db_connection_id=4, source="science",
            period_from=date(2026, 1, 1), period_to=date(2026, 3, 31),
        )
    assert len(docs) == 2
    assert docs[0].source == "science"
    assert docs[0].doc_id == "1"
    assert "quantum" in docs[0].text
    assert docs[0].timestamp == date(2026, 1, 15)
    assert "quantum" in docs[0].entities  # keyword 拆为实体


@pytest.mark.asyncio
async def test_load_skips_rows_missing_timestamp():
    conn, _ = _fake_conn()
    cur = conn.cursor.return_value
    cur.fetchall.return_value = [
        (1, "ok title", "abs", "kw", date(2026, 1, 1)),
        (2, "no date", "abs", "kw", None),  # timestamp 缺失 → 跳过
    ]
    p_sess, p_dsn = _patch_db_resolver()
    with p_sess, p_dsn, patch(_P_PYMYSQL, return_value=conn):
        docs = await CorpusLoader().load(4, "science", date(2026, 1, 1), date(2026, 3, 31))
    assert len(docs) == 1


@pytest.mark.asyncio
async def test_load_connect_error_returns_empty():
    p_sess, p_dsn = _patch_db_resolver()
    with p_sess, p_dsn, patch(
        _P_PYMYSQL, side_effect=Exception("connect failed"),
    ):
        docs = await CorpusLoader().load(4, "science", date(2026, 1, 1), date(2026, 3, 31))
    assert docs == []  # 单源失败不抛，降级空


@pytest.mark.asyncio
async def test_load_unknown_source_returns_empty():
    p_sess, p_dsn = _patch_db_resolver()
    with p_sess, p_dsn:
        docs = await CorpusLoader().load(4, "bogus", date(2026, 1, 1), date(2026, 3, 31))
    assert docs == []


@pytest.mark.asyncio
async def test_load_db_connection_not_found_returns_empty():
    """session.get(...) 返回 None → dsn 为 None → 返回空，不开 pymysql 连接。"""
    fake_session = MagicMock()
    fake_session.get = AsyncMock(return_value=None)
    fake_ctx = MagicMock()
    fake_ctx.__aenter__ = AsyncMock(return_value=fake_session)
    fake_ctx.__aexit__ = AsyncMock(return_value=False)

    with patch(
        _P_GET_SESSION, return_value=fake_ctx
    ), patch(
        _P_RESOLVE_DSN
    ) as p_dsn:
        docs = await CorpusLoader().load(999, "science", date(2026, 1, 1), date(2026, 3, 31))
    assert docs == []
    p_dsn.assert_not_called()  # ORM 没找到，resolve_dsn 不应被调用
