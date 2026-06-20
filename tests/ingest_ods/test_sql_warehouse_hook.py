from unittest.mock import MagicMock, patch


def _src(cfg: dict):
    s = MagicMock()
    s.config_json = cfg
    return s


def test_hook_enqueues_when_enabled():
    from metaprofile.ingest_ods.collectors import sql_warehouse
    src = _src({"enable_weak_signal": True, "db_connection_id": 4})
    with patch("metaprofile.shared.worker.newtech_tasks.extract_weak_signals") as t:
        sql_warehouse._maybe_trigger_weak_signal(src, imported=5)
    t.delay.assert_called_once()
    # delay 实参:period_from, period_to, domain, db_connection_id
    args = t.delay.call_args.args
    assert args[2] is None and args[3] == 4


def test_hook_skipped_when_disabled():
    from metaprofile.ingest_ods.collectors import sql_warehouse
    src = _src({"enable_weak_signal": False, "db_connection_id": 4})
    with patch("metaprofile.shared.worker.newtech_tasks.extract_weak_signals") as t:
        sql_warehouse._maybe_trigger_weak_signal(src, imported=5)
    t.delay.assert_not_called()


def test_hook_skipped_when_no_import():
    from metaprofile.ingest_ods.collectors import sql_warehouse
    src = _src({"enable_weak_signal": True, "db_connection_id": 4})
    with patch("metaprofile.shared.worker.newtech_tasks.extract_weak_signals") as t:
        sql_warehouse._maybe_trigger_weak_signal(src, imported=0)  # 无新行 → 不触发
    t.delay.assert_not_called()


def test_hook_skipped_when_no_db_connection():
    from metaprofile.ingest_ods.collectors import sql_warehouse
    src = _src({"enable_weak_signal": True})  # 无 db_connection_id
    with patch("metaprofile.shared.worker.newtech_tasks.extract_weak_signals") as t:
        sql_warehouse._maybe_trigger_weak_signal(src, imported=5)
    t.delay.assert_not_called()


def test_hook_failure_is_swallowed():
    """Celery 入队抛错 → 仅告警，不向上抛（不杀灌库结果）。"""
    from metaprofile.ingest_ods.collectors import sql_warehouse
    src = _src({"enable_weak_signal": True, "db_connection_id": 4})
    with patch("metaprofile.shared.worker.newtech_tasks.extract_weak_signals") as t:
        t.delay.side_effect = Exception("broker down")
        sql_warehouse._maybe_trigger_weak_signal(src, imported=5)  # 不抛
