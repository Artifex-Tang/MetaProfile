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
