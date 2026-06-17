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
