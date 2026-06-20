from datetime import datetime, timezone

import pytest

from metaprofile.shared.scheduler.poller import is_due


def test_is_due_true_when_cron_passed_since_last_run():
    last = datetime(2026, 6, 20, 0, 0, tzinfo=timezone.utc)
    now = datetime(2026, 6, 20, 3, 0, tzinfo=timezone.utc)  # 3h 后，0 2 * * * 已过
    assert is_due("0 2 * * *", last, now) is True


def test_is_due_false_before_next_fire():
    last = datetime(2026, 6, 20, 2, 5, tzinfo=timezone.utc)  # 2:00 刚跑(记 2:05)
    now = datetime(2026, 6, 20, 2, 30, tzinfo=timezone.utc)   # 下次 2:00 明天
    assert is_due("0 2 * * *", last, now) is False


def test_is_due_no_last_run_uses_epoch():
    now = datetime(2026, 6, 20, 3, 0, tzinfo=timezone.utc)
    assert is_due("0 2 * * *", None, now) is True


def test_is_due_invalid_cron_raises():
    with pytest.raises(ValueError):
        is_due("not a cron", datetime(2026, 6, 20, tzinfo=timezone.utc),
               datetime(2026, 6, 20, 3, tzinfo=timezone.utc))


from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_tick_dispatches_due_task_and_updates_last_run():
    from metaprofile.shared.scheduler import poller

    task = MagicMock()
    task.id = 1
    task.name = "nightly-translate"
    task.task_type = "translate_batch"
    task.cron = "0 2 * * *"
    task.params = {"entity_type": "tech"}
    task.enabled = True
    task.last_run_at = None

    fake_result = MagicMock()
    fake_result.scalars.return_value.all.return_value = [task]
    session = AsyncMock()
    session.execute = AsyncMock(return_value=fake_result)

    dispatched = []
    with patch.object(poller, "dispatch", AsyncMock(side_effect=lambda **k: dispatched.append(k) or "celery-id")):
        summary = await poller.tick(session, now=datetime(2026, 6, 20, 3, 0, tzinfo=timezone.utc))
    assert summary["dispatched"] == 1
    assert task.last_status == "ok"
    assert task.last_run_at is not None
    assert dispatched == [{"task_type": "translate_batch", "params": {"entity_type": "tech"}}]


@pytest.mark.asyncio
async def test_tick_skips_not_due():
    from metaprofile.shared.scheduler import poller
    task = MagicMock()
    task.cron = "0 2 * * *"
    task.enabled = True
    task.last_run_at = datetime(2026, 6, 20, 2, 5, tzinfo=timezone.utc)
    fake_result = MagicMock(); fake_result.scalars.return_value.all.return_value = [task]
    session = AsyncMock(); session.execute = AsyncMock(return_value=fake_result)
    with patch.object(poller, "dispatch", AsyncMock()) as d:
        summary = await poller.tick(session, now=datetime(2026, 6, 20, 2, 30, tzinfo=timezone.utc))
    assert summary["dispatched"] == 0
    d.assert_not_called()


@pytest.mark.asyncio
async def test_tick_failed_task_marks_failed_not_raise():
    from metaprofile.shared.scheduler import poller
    task = MagicMock()
    task.cron = "0 2 * * *"; task.enabled = True; task.last_run_at = None
    task.task_type = "translate_batch"; task.params = {}
    fake_result = MagicMock(); fake_result.scalars.return_value.all.return_value = [task]
    session = AsyncMock(); session.execute = AsyncMock(return_value=fake_result)
    with patch.object(poller, "dispatch", AsyncMock(side_effect=Exception("broker down"))):
        summary = await poller.tick(session, now=datetime(2026, 6, 20, 3, 0, tzinfo=timezone.utc))
    assert summary["dispatched"] == 0  # 该任务失败未计入
    assert task.last_status == "failed"


def test_dispatch_registry_has_translate_batch():
    from metaprofile.shared.scheduler import poller
    poller._ensure_registry()
    assert "translate_batch" in poller.TASK_DISPATCH
