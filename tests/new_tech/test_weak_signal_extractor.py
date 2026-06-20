"""T8 单元测试：WeakSignalExtractor.extract 语料驱动端到端 + 落库。

AdaptiveThreshold 被 patch（fake db 无历史 strength 分布），返回 0.0 让所有候选通过。
corpus_loader 通过构造器注入（fake_loader.load 对 4 源都返回同一批 docs）。
"""
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metaprofile.new_tech_discovery.services.corpus_loader import CorpusDoc
from metaprofile.new_tech_discovery.services.weak_signal_extractor import WeakSignalExtractor

_WS_MODULE = "metaprofile.new_tech_discovery.services.weak_signal_extractor"


def _docs_with_rising_term():
    """构造：'quantum' 在当前期突现 + 多源，应被提取为弱信号。"""
    docs = []
    # 历史（2025-11/12）低频
    for m in (11, 12):
        docs.append(CorpusDoc("science", f"h{m}", "quantum baseline",
                              date(2025, m, 10), []))
    # 当前期（2026-01/02/03）多源高频突现
    docs.append(CorpusDoc("science", "c1", "quantum breakthrough",
                          date(2026, 1, 5), ["quantum"]))
    docs.append(CorpusDoc("patent", "c2", "quantum chip patent",
                          date(2026, 2, 5), ["ACME"]))
    docs.append(CorpusDoc("market", "c3", "quantum procurement",
                          date(2026, 3, 5), ["BUYER"]))
    return docs


def _fake_db():
    fake_db = MagicMock()
    added_signals = []
    fake_db.add = MagicMock(side_effect=lambda orm: added_signals.append(orm))
    fake_db.flush = AsyncMock()
    fake_db.commit = AsyncMock()
    return fake_db, added_signals


@pytest.mark.asyncio
@patch(f"{_WS_MODULE}.AdaptiveThreshold")
async def test_extract_emits_signal_for_rising_term(mock_adaptive_cls):
    mock_adaptive_cls.return_value.compute = AsyncMock(return_value=0.0)
    docs = _docs_with_rising_term()
    fake_loader = AsyncMock()
    fake_loader.load = AsyncMock(return_value=docs)

    fake_db, added_signals = _fake_db()

    ext = WeakSignalExtractor(corpus_loader=fake_loader, db_connection_id=4)
    signals = await ext.extract(
        db=fake_db, domain=None,
        period_from=date(2026, 1, 1), period_to=date(2026, 3, 31),
    )

    # quantum 应至少产出一条弱信号
    assert len(signals) >= 1
    kw_union = {k for s in signals for k in s.keywords}
    assert "quantum" in kw_union
    # 每条信号有 [0,1] 强度与四维
    for s in signals:
        assert 0.0 <= s.strength <= 1.0
        assert 0.0 <= s.novelty <= 1.0
    # 落库 ORM 已 add
    assert len(added_signals) == len(signals)
    assert added_signals[0].signal_id.startswith("WS-")


@pytest.mark.asyncio
@patch(f"{_WS_MODULE}.AdaptiveThreshold")
async def test_extract_empty_corpus_returns_empty(mock_adaptive_cls):
    mock_adaptive_cls.return_value.compute = AsyncMock(return_value=0.0)
    fake_loader = AsyncMock()
    fake_loader.load = AsyncMock(return_value=[])
    fake_db, _ = _fake_db()
    ext = WeakSignalExtractor(corpus_loader=fake_loader, db_connection_id=4)
    signals = await ext.extract(db=fake_db, domain=None,
                                period_from=date(2026, 1, 1), period_to=date(2026, 3, 31))
    assert signals == []


@pytest.mark.asyncio
@patch(f"{_WS_MODULE}.AdaptiveThreshold")
async def test_extract_signal_id_deterministic_dedup(mock_adaptive_cls):
    """同 keyword 集合 → 同 signal_id（幂等去重）。"""
    mock_adaptive_cls.return_value.compute = AsyncMock(return_value=0.0)
    docs = _docs_with_rising_term()
    fake_loader = AsyncMock()
    fake_loader.load = AsyncMock(return_value=docs)
    fake_db1, _ = _fake_db()
    fake_db2, _ = _fake_db()
    ext = WeakSignalExtractor(corpus_loader=fake_loader, db_connection_id=4)
    s1 = await ext.extract(
        db=fake_db1, domain=None,
        period_from=date(2026, 1, 1), period_to=date(2026, 3, 31),
    )
    s2 = await ext.extract(
        db=fake_db2, domain=None,
        period_from=date(2026, 1, 1), period_to=date(2026, 3, 31),
    )
    assert [x.signal_id for x in s1] == [x.signal_id for x in s2]
