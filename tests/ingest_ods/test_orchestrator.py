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
