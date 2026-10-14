"""Phase A1/A2/A6:语料源对 Doris DDL 对齐 + 新源 + industry 过滤 + attachment 可选。

Ddl 对齐测试(A6)直接解析仓库根 `_doris_local_schema.sql`,防止再出现 pubdate/
Inventor 这类"spec 列名不在真实 DDL"的漂移(spec 2026-10-14 §4.1 G1-G3)。
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from metaprofile.new_tech_discovery.services.corpus_loader import CorpusLoader

_MOD = "metaprofile.new_tech_discovery.services.corpus_loader"
_P_GET_SESSION = f"{_MOD}.get_session"
_P_RESOLVE_DSN = f"{_MOD}.resolve_dsn"
_P_PYMYSQL = f"{_MOD}.pymysql.connect"


@pytest.fixture(autouse=True)
def _clear_missing_tables_cache():
    """隔离模块级 _MISSING_TABLES 缓存,防测试间顺序依赖(审查 L15)。"""
    from metaprofile.new_tech_discovery.services import corpus_loader

    saved = set(corpus_loader._MISSING_TABLES)
    corpus_loader._MISSING_TABLES.clear()
    yield
    corpus_loader._MISSING_TABLES.clear()
    corpus_loader._MISSING_TABLES.update(saved)


def _parse_doris_ddl() -> dict[str, set[str]]:
    schema = Path(__file__).resolve().parents[2] / "_doris_local_schema.sql"
    text = schema.read_text(encoding="utf-8")
    tables: dict[str, set[str]] = {}
    for m in re.finditer(r"CREATE TABLE `(\w+)` \((.*?)\)\s*ENGINE", text, re.S):
        cols = set(re.findall(r"^\s*`(\w+)`", m.group(2), re.M))
        tables[m.group(1)] = cols
    return tables


def _fake_session_ctx():
    from unittest.mock import AsyncMock

    fake_session = MagicMock()
    fake_session.get = AsyncMock(return_value=MagicMock(name="fake_orm"))
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=fake_session)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return patch(_P_GET_SESSION, return_value=ctx)


_DSN = {"host": "x", "port": 1, "user": "u", "password": "p", "database": "d"}


def test_source_specs_align_with_doris_ddl():
    """A6:非可选源的表/文本列/时间列/实体列必须全部存在于 Doris DDL。"""
    from metaprofile.new_tech_discovery.services.corpus_loader import (
        _OPTIONAL_SOURCES,
        _SOURCE_SPECS,
    )

    ddl = _parse_doris_ddl()
    expected = {
        "science", "patent", "market", "policy",
        "key_events", "industry_report", "intl_news",
    }
    assert expected <= set(_SOURCE_SPECS), f"缺源:{expected - set(_SOURCE_SPECS)}"
    for src, spec in _SOURCE_SPECS.items():
        if src in _OPTIONAL_SOURCES:
            continue  # 可选源(attachment)表未建,不比对
        assert spec.table in ddl, f"{src}:表 {spec.table} 不在 Doris DDL"
        used = set(list(spec.text_cols) + list(spec.ent_cols) + [spec.time_col])
        missing = used - ddl[spec.table]
        assert not missing, f"{src}:列 {missing} 不在 {spec.table} DDL"


def test_science_time_col_is_event_time():
    """A1/G1:science 源时间列必须为 event_time(原 pubdate 不存在)。"""
    from metaprofile.new_tech_discovery.services.corpus_loader import _SOURCE_SPECS

    assert _SOURCE_SPECS["science"].time_col == "event_time"


def test_patent_entity_cols_exist_in_ddl():
    """A1/G2:patent 实体列不得含 DDL 外的 Inventor。"""
    from metaprofile.new_tech_discovery.services.corpus_loader import _SOURCE_SPECS

    ddl = _parse_doris_ddl()
    spec = _SOURCE_SPECS["patent"]
    assert not (set(spec.ent_cols) - ddl[spec.table])


@pytest.mark.asyncio
async def test_load_policy_source_maps_to_corpus_doc():
    """A2:policy 源可加载,实体=policy_source。"""
    conn = MagicMock()
    cur = MagicMock()
    cur.description = [("id",), ("title",), ("policy_source",), ("event_time",)]
    cur.fetchall.return_value = [
        (1, "某国发布量子战略", "科技部", date(2026, 2, 1)),
    ]
    conn.cursor.return_value = cur
    with _fake_session_ctx(), patch(_P_RESOLVE_DSN, return_value=_DSN), \
         patch(_P_PYMYSQL, return_value=conn):
        docs = await CorpusLoader().load(
            4, "policy", date(2026, 1, 1), date(2026, 3, 31),
        )
    assert len(docs) == 1
    assert docs[0].source == "policy"
    assert docs[0].entities == ["科技部"]


@pytest.mark.asyncio
async def test_load_industry_filter_in_sql_and_params():
    """A2:传 industry → SQL 带 `industry` = %s 且参数含该值。"""
    conn = MagicMock()
    cur = MagicMock()
    cur.description = [("id",), ("title",), ("event_time",)]
    cur.fetchall.return_value = []
    conn.cursor.return_value = cur
    with _fake_session_ctx(), patch(_P_RESOLVE_DSN, return_value=_DSN), \
         patch(_P_PYMYSQL, return_value=conn):
        docs = await CorpusLoader().load(
            4, "key_events", date(2026, 1, 1), date(2026, 3, 31),
            industry="人工智能",
        )
    assert docs == []
    sql, params = cur.execute.call_args[0]
    assert "`industry` = %s" in sql
    assert "人工智能" in params


@pytest.mark.asyncio
async def test_load_optional_source_missing_table_skips_cleanly():
    """A1/G3:attachment 表不存在 → 探测后返回 [],不产生 error 日志/异常。"""
    conn = MagicMock()
    cur = MagicMock()
    cur.description = [("Tables_in_d",)]
    cur.fetchall.return_value = []  # SHOW TABLES 无命中
    conn.cursor.return_value = cur
    with _fake_session_ctx(), patch(_P_RESOLVE_DSN, return_value=_DSN), \
         patch(_P_PYMYSQL, return_value=conn):
        docs = await CorpusLoader().load(
            4, "attachment", date(2026, 1, 1), date(2026, 3, 31),
        )
    assert docs == []
    assert cur.execute.call_count == 1  # 只探测,不跑语料 SQL
