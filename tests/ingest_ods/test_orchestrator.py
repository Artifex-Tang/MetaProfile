from unittest.mock import AsyncMock, MagicMock

import pytest

from metaprofile.ingest_ods.services.orchestrator import (
    BatchOrchestrator,
    _active_types,
    compute_entity_id,
)
from metaprofile.ingest_ods.services.watermark import WatermarkStore


def _source(tables, workers=2, batch=10, mode="structured_only"):
    s = MagicMock()
    s.id = 1
    s.profile_type = "all"
    s.config_json = {"table_set": tables, "workers": workers, "batch_size": batch,
                     "watermark_col": "update_time", "mode": mode,
                     "db_connection_id": 1, "profile_types": ["all"]}
    return s


def _make_deps(rows_by_table):
    """rows_by_table: {table: [list of rows]}; each call to extract_batch pops the
    next batch list per table. Returns (extractor, resolver, scorer, writer, session)."""
    extractor = AsyncMock()

    async def _extract(dsn, table, last_id, batch_size, watermark):
        return rows_by_table[table].pop(0) if rows_by_table[table] else []
    extractor.extract_batch = AsyncMock(side_effect=_extract)

    resolver = AsyncMock()
    resolver.resolve = AsyncMock(side_effect=lambda rows: [
        {"profile_type": r["profile_type"], "entity_key": r["entity_key"],
         "attrs": r["raw_payload"]["_attrs"], "source_rows": [r]}
        for r in rows
    ])
    scorer = AsyncMock()
    scorer.score = AsyncMock(return_value={"veracity_score": 0.9,
                                           "timeliness_score": 0.5,
                                           "data_as_of": None})
    writer = AsyncMock()
    writer.write_profile = AsyncMock(return_value="E1")
    conn_orm = MagicMock()
    conn_orm.host = "h"; conn_orm.port = 9030
    conn_orm.username = "u"; conn_orm.password_enc = "p"; conn_orm.database = "d"
    conn_orm.charset = "utf8mb4"
    session = AsyncMock()
    session.get = AsyncMock(return_value=conn_orm)
    return extractor, resolver, scorer, writer, session


@pytest.mark.asyncio
async def test_run_processes_batches_and_advances_watermark() -> None:
    src = _source(["ods_company_basic_info"])
    extractor = AsyncMock()
    extractor.extract_batch = AsyncMock(side_effect=[
        [{"profile_type": "org", "entity_key": {"company_id": 1},
          "raw_payload": {"_attrs": {"name_cn": "甲"}}, "source_id": "1", "last_id": 5}],
        [],  # 第二批空 → 结束
    ])
    resolver = AsyncMock(); resolver.resolve = AsyncMock(side_effect=lambda rows: [
        {"profile_type": r["profile_type"], "entity_key": r["entity_key"],
         "attrs": r["raw_payload"]["_attrs"], "source_rows": [r]}
        for r in rows
    ])
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
    # C2: watermark last_id 按表命名空间
    assert WatermarkStore.get(src, "last_id:ods_company_basic_info") == 5
    writer.write_profile.assert_awaited()


@pytest.mark.asyncio
async def test_same_profile_type_is_mutex() -> None:
    assert "org" not in _active_types


@pytest.mark.asyncio
async def test_watermark_namespaced_per_table() -> None:
    """C2: 两表 source，last_id 独立存储不被覆盖。"""
    src = _source(["ods_company_basic_info", "ods_talent_info_cn"])
    rows_by_table = {
        "ods_company_basic_info": [
            [{"profile_type": "org", "entity_key": {"company_id": 1},
              "raw_payload": {"_attrs": {"name_cn": "甲"}},
              "source_id": "1", "last_id": 100}],
            [],
        ],
        "ods_talent_info_cn": [
            [{"profile_type": "person", "entity_key": {"orcid": "0001"},
              "raw_payload": {"_attrs": {"name_cn": "李四"}},
              "source_id": "1", "last_id": 7}],
            [],
        ],
    }
    extractor, resolver, scorer, writer, session = _make_deps(rows_by_table)

    orch = BatchOrchestrator(extractor=extractor, resolver=resolver, scorer=scorer,
                             writer=writer, connections=lambda c: {})
    await orch.run(session, task=MagicMock(id=7), source=src)

    assert WatermarkStore.get(src, "last_id:ods_company_basic_info") == 100
    assert WatermarkStore.get(src, "last_id:ods_talent_info_cn") == 7
    # 旧的全局 last_id 不应存在（防止回归到共享 key）
    assert WatermarkStore.get(src, "last_id") is None


@pytest.mark.asyncio
async def test_unmapped_table_skipped_with_warning() -> None:
    """I1: 未映射表跳过，extract_batch 不被调用。"""
    # ods_strategic_policy_cn 未映射；ods_company_basic_info 已映射
    src = _source(["ods_strategic_policy_cn", "ods_company_basic_info"])
    rows_by_table = {
        "ods_company_basic_info": [
            [{"profile_type": "org", "entity_key": {"company_id": 1},
              "raw_payload": {"_attrs": {"name_cn": "甲"}},
              "source_id": "1", "last_id": 5}],
            [],
        ],
    }
    extractor, resolver, scorer, writer, session = _make_deps(rows_by_table)

    # 追踪 extract_batch 被哪些 table 调用
    called_tables: list[str] = []
    orig_extract = extractor.extract_batch

    async def _tracking_extract(dsn, table, last_id, batch_size, watermark):
        called_tables.append(table)
        return await orig_extract(dsn, table=table, last_id=last_id,
                                  batch_size=batch_size, watermark=watermark)
    extractor.extract_batch = AsyncMock(side_effect=_tracking_extract)

    orch = BatchOrchestrator(extractor=extractor, resolver=resolver, scorer=scorer,
                             writer=writer, connections=lambda c: {})
    await orch.run(session, task=MagicMock(id=7), source=src)

    assert "ods_strategic_policy_cn" not in called_tables
    assert "ods_company_basic_info" in called_tables
    # 未映射表未写任何 watermark
    assert WatermarkStore.get(src, "last_id:ods_strategic_policy_cn") is None


@pytest.mark.parametrize("entity_key, attrs, expected", [
    # org with company_id 强键
    ({"company_id": 1}, {"name_cn": "甲"}, "1"),
    # person name-only 兜底
    ({}, {"name_cn": "李四"}, "name:李四"),
    # project list name_cn → 归一首元素，不是 list repr
    ({}, {"name_cn": ["M1"]}, "name:M1"),
    # tech_name_cn 兜底 + list
    ({}, {"tech_name_cn": ["T1", "T2"]}, "name:T1"),
    # 空列表 name → 无身份
    ({}, {"name_cn": []}, None),
    # 无强键无 name → None
    ({}, {}, None),
    # 强键优先级：company_id 高于 usc_code
    ({"company_id": 1, "usc_code": "91110"}, {}, "1"),
    # orcid 强键
    ({"orcid": "0000-0001"}, {}, "0000-0001"),
])
def test_compute_entity_id(entity_key, attrs, expected) -> None:
    assert compute_entity_id(entity_key, attrs) == expected
