"""单元测试：shared/worker/newtech_tasks —— 弱信号提取 celery 任务。

隔离策略（同 tests/test_enrich_tasks.py T6 模式）：
- patch.get_session 为 AsyncMock ctx mgr，yield MagicMock session
- patch WeakSignalExtractor / NetworkCorrelator
- MagicMock session.execute 返回 .scalars().all() → []，故 correlator 循环不触发
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from metaprofile.shared.worker import newtech_tasks


def _patch_session():
    """构造可 patch.object(newtech_tasks, 'get_session', return_value=cm) 的 ctx mgr。"""
    fake_session = MagicMock()
    # select(WeakSignalORM).where(...).scalars().all() → []
    fake_session.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))
    )
    fake_session.commit = AsyncMock()
    cm = AsyncMock()
    cm.__aenter__.return_value = fake_session
    cm.__aexit__.return_value = None
    return cm, fake_session


def test_extract_weak_signals_runs_async_and_returns_done():
    fake_ext = MagicMock()
    fake_ext.extract = AsyncMock(return_value=[])

    cm, _ = _patch_session()
    with patch.object(newtech_tasks, "get_session", return_value=cm), \
         patch.object(newtech_tasks, "WeakSignalExtractor", return_value=fake_ext), \
         patch.object(newtech_tasks, "NetworkCorrelator") as net_cls:
        net_inst = MagicMock()
        net_inst.build_network = AsyncMock(return_value=[])
        net_cls.return_value = net_inst

        result = newtech_tasks.extract_weak_signals(
            period_from="2026-01-01", period_to="2026-03-31",
            domain=None, db_connection_id=4,
        )

    assert result["status"] == "done"
    assert result["signals"] == 0
    assert result["edges"] == 0
    fake_ext.extract.assert_awaited_once()
    # 空 rows → correlator 实例化但 build_network 不应被调用
    net_inst.build_network.assert_not_awaited()


def test_extract_weak_signals_handles_exception():
    fake_ext = MagicMock()
    fake_ext.extract = AsyncMock(side_effect=Exception("boom"))

    cm, _ = _patch_session()
    with patch.object(newtech_tasks, "get_session", return_value=cm), \
         patch.object(newtech_tasks, "WeakSignalExtractor", return_value=fake_ext):
        result = newtech_tasks.extract_weak_signals(
            "2026-01-01", "2026-03-31", None, 4,
        )

    assert result["status"] == "failed"
    assert "boom" in result["error"]
