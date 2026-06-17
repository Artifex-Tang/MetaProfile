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

    # get_session is lazy-imported INSIDE run_sql_warehouse_collection
    # (`from metaprofile.shared.db.postgres import get_session`), so it is
    # NOT bound at sw module level — patching sw.get_session raises
    # AttributeError. Patch at the SOURCE module the lazy import reads from.
    with patch("metaprofile.shared.db.postgres.get_session", _ctx(session)), \
         patch.object(sw, "BatchOrchestrator", return_value=orch):
        n = await sw.run_sql_warehouse_collection(task=MagicMock(id=7), source=source)
    assert n == 1
    writer.write_profile.assert_awaited()


class _ctx:
    """Async-context-manager factory matching the real get_session() shape.

    The real ``get_session`` is CALLED (``async with get_session() as sess``)
    and returns an async context manager. So a patched replacement must be
    callable and yield the session from __aenter__. An instance whose
    __call__ returns itself satisfies both: ``_ctx(sess)()`` → the instance,
    which then behaves as the async CM.
    """
    def __init__(self, session): self.s = session
    def __call__(self): return self
    async def __aenter__(self): return self.s
    async def __aexit__(self, *a): return False
