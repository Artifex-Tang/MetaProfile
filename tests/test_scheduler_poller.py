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
