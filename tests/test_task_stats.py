"""单元测试：采集任务运行统计（ingest_raw / ingest_errors 聚合）。"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.mark.asyncio
async def test_get_task_stats_aggregates_raw_and_errors():
    from metaprofile.settings_api.services.collector_service import get_task_stats

    db = AsyncMock()
    counts = iter([100, 5, 3])  # raw_total, raw_failed, errors

    async def _exec(_stmt):
        r = MagicMock()
        r.scalar_one.return_value = next(counts)
        return r

    db.execute = _exec

    stats = await get_task_stats(db, 7)
    assert stats.task_id == 7
    assert stats.raw_total == 100
    assert stats.raw_failed == 5
    assert stats.raw_success == 95
    assert stats.errors == 3
