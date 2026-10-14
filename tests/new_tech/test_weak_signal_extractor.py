"""T8 单元测试:WeakSignalExtractor.extract 语料驱动端到端 + 落库。

AdaptiveThreshold 被 patch(fake db 无历史 strength 分布),返回 0.0 让所有候选通过。
corpus_loader 通过构造器注入(fake_loader.load 按 source 分流,仅 science 返回 docs
—— extractor 现在遍历 8 源,同一批 docs 重复 8 次会扭曲计数)。

Phase A(2026-10-14)新增断言:证据链回填(evidence_doc_ids/related_*)、
真共现边(signal↔signal)、term_stats 持久化调用。
"""
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metaprofile.new_tech_discovery.domain.orm_models import (
    SignalNetworkEdgeORM,
    WeakSignalORM,
)
from metaprofile.new_tech_discovery.services.corpus_loader import CorpusDoc
from metaprofile.new_tech_discovery.services.weak_signal_extractor import WeakSignalExtractor

_WS_MODULE = "metaprofile.new_tech_discovery.services.weak_signal_extractor"


def _docs_with_rising_term():
    """构造:'quantum' 在当前期突现 + 多源,应被提取为弱信号。"""
    docs = []
    # 历史(2025-11/12)低频
    for m in (11, 12):
        docs.append(CorpusDoc("science", f"h{m}", "quantum baseline",
                              date(2025, m, 10), []))
    # 当前期(2026-01/02/03)多源高频突现
    docs.append(CorpusDoc("science", "c1", "quantum breakthrough",
                          date(2026, 1, 5), ["quantum"]))
    docs.append(CorpusDoc("patent", "c2", "quantum chip patent",
                          date(2026, 2, 5), ["ACME"]))
    docs.append(CorpusDoc("market", "c3", "quantum procurement",
                          date(2026, 3, 5), ["BUYER"]))
    return docs


def _fake_loader(docs, source_with="science"):
    """load(db_id, source, pf, pt, *, industry, session) → 仅 source_with 返回 docs。"""
    async def _load(db_id, source, pf, pt, *, industry=None, session=None):
        return docs if source == source_with else []
    loader = MagicMock()
    loader.load = AsyncMock(side_effect=_load)
    return loader


def _fake_db():
    fake_db = MagicMock()
    added = []
    fake_db.add = MagicMock(side_effect=lambda orm: added.append(orm))
    fake_db.flush = AsyncMock()
    fake_db.commit = AsyncMock()
    fake_db.new = set()  # _link_evidence 回写遍历用
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    fake_db.execute = AsyncMock(return_value=result)
    return fake_db, added


@pytest.mark.asyncio
@patch(f"{_WS_MODULE}.AdaptiveThreshold")
@patch(f"{_WS_MODULE}.persist_term_stats", new_callable=AsyncMock)
async def test_extract_emits_signal_for_rising_term(mock_persist, mock_adaptive_cls):
    mock_adaptive_cls.return_value.compute = AsyncMock(return_value=0.0)
    docs = _docs_with_rising_term()

    fake_db, added_signals = _fake_db()

    ext = WeakSignalExtractor(
        corpus_loader=_fake_loader(docs), db_connection_id=4,
    )
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
    # 落库 ORM 已 add(过滤掉共现边等其它 add 对象)
    added_orms = [o for o in added_signals if isinstance(o, WeakSignalORM)]
    assert len(added_orms) == len(signals)
    assert added_orms[0].signal_id.startswith("WS-")
    # A3:term_stats 持久化被调用
    mock_persist.assert_awaited()


@pytest.mark.asyncio
@patch(f"{_WS_MODULE}.AdaptiveThreshold")
async def test_extract_empty_corpus_returns_empty(mock_adaptive_cls):
    mock_adaptive_cls.return_value.compute = AsyncMock(return_value=0.0)
    fake_db, _ = _fake_db()
    ext = WeakSignalExtractor(corpus_loader=_fake_loader([]), db_connection_id=4)
    signals = await ext.extract(db=fake_db, domain=None,
                                period_from=date(2026, 1, 1), period_to=date(2026, 3, 31))
    assert signals == []


@pytest.mark.asyncio
@patch(f"{_WS_MODULE}.AdaptiveThreshold")
async def test_extract_signal_id_deterministic_dedup(mock_adaptive_cls):
    """同 keyword 集合 → 同 signal_id(幂等去重)。"""
    mock_adaptive_cls.return_value.compute = AsyncMock(return_value=0.0)
    docs = _docs_with_rising_term()
    loader = _fake_loader(docs)
    fake_db1, _ = _fake_db()
    fake_db2, _ = _fake_db()
    ext = WeakSignalExtractor(corpus_loader=loader, db_connection_id=4)
    s1 = await ext.extract(
        db=fake_db1, domain=None,
        period_from=date(2026, 1, 1), period_to=date(2026, 3, 31),
    )
    s2 = await ext.extract(
        db=fake_db2, domain=None,
        period_from=date(2026, 1, 1), period_to=date(2026, 3, 31),
    )
    assert [x.signal_id for x in s1] == [x.signal_id for x in s2]


@pytest.mark.asyncio
@patch(f"{_WS_MODULE}.AdaptiveThreshold")
async def test_extract_passes_domain_as_industry_filter(mock_adaptive_cls):
    """domain 参数 → loader 的 industry 过滤(G9/A2)。"""
    mock_adaptive_cls.return_value.compute = AsyncMock(return_value=0.0)
    loader = _fake_loader([])
    fake_db, _ = _fake_db()
    ext = WeakSignalExtractor(corpus_loader=loader, db_connection_id=4)
    await ext.extract(db=fake_db, domain="人工智能",
                      period_from=date(2026, 1, 1), period_to=date(2026, 3, 31))
    for call in loader.load.await_args_list:
        assert call.kwargs.get("industry") == "人工智能"


@pytest.mark.asyncio
@patch(f"{_WS_MODULE}.AdaptiveThreshold")
async def test_extract_fills_evidence_doc_ids(mock_adaptive_cls):
    """A4:信号 evidence_doc_ids 来自 term 命中文档(最近 cap 篇)。"""
    mock_adaptive_cls.return_value.compute = AsyncMock(return_value=0.0)
    docs = _docs_with_rising_term()
    fake_db, added = _fake_db()
    ext = WeakSignalExtractor(corpus_loader=_fake_loader(docs), db_connection_id=4)
    signals = await ext.extract(
        db=fake_db, domain=None,
        period_from=date(2026, 1, 1), period_to=date(2026, 3, 31),
    )
    quantum = next(s for s in signals if "quantum" in s.keywords)
    assert quantum.evidence_doc_ids  # 非空:至少含命中的 c1
    orm = next(o for o in added if isinstance(o, WeakSignalORM)
               and o.signal_id == quantum.signal_id)
    assert orm.evidence_doc_ids == quantum.evidence_doc_ids


@pytest.mark.asyncio
@patch(f"{_WS_MODULE}.AdaptiveThreshold")
async def test_extract_links_related_profiles_from_evidence_entities(mock_adaptive_cls):
    """A4:证据文档实体 → org/person/tech 画像 id(db 命中即回填)。"""
    from metaprofile.new_tech_discovery.services import weak_signal_extractor as wse

    mock_adaptive_cls.return_value.compute = AsyncMock(return_value=0.0)
    docs = _docs_with_rising_term()

    org_row = MagicMock()
    org_row.org_id = "ORG-9"
    fake_db, _ = _fake_db()
    fake_db.execute = AsyncMock(
        return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(
            all=MagicMock(return_value=["ORG-9"]),
        )))
    )
    with patch.object(wse.EntityLinker, "link_persons", new=AsyncMock(return_value=[])), \
         patch.object(wse.EntityLinker, "link_techs", new=AsyncMock(return_value=[])):
        ext = WeakSignalExtractor(corpus_loader=_fake_loader(docs), db_connection_id=4)
        signals = await ext.extract(
            db=fake_db, domain=None,
            period_from=date(2026, 1, 1), period_to=date(2026, 3, 31),
        )
    # c1 实体含 "quantum";org 链接器返回 ORG-9 → 至少一条信号带 org 关联
    assert any(s.related_org_ids == ["ORG-9"] for s in signals)


@pytest.mark.asyncio
@patch(f"{_WS_MODULE}.AdaptiveThreshold")
async def test_extract_writes_cooccurrence_edges(mock_adaptive_cls):
    """A5:同文档 ≥2 信号词 → signal↔signal co_occurrence 边。"""
    mock_adaptive_cls.return_value.compute = AsyncMock(return_value=0.0)
    docs = [
        CorpusDoc("science", "1", "quantum chip", date(2026, 1, 5), []),
        CorpusDoc("science", "2", "quantum chip", date(2026, 2, 5), []),
        CorpusDoc("science", "3", "quantum sensor", date(2026, 3, 5), []),
    ]
    fake_db, added = _fake_db()
    ext = WeakSignalExtractor(corpus_loader=_fake_loader(docs), db_connection_id=4)
    signals = await ext.extract(
        db=fake_db, domain=None,
        period_from=date(2026, 1, 1), period_to=date(2026, 3, 31),
    )
    edges = [o for o in added if isinstance(o, SignalNetworkEdgeORM)]
    assert edges, "应产出至少一条共现边"
    for e in edges:
        assert e.edge_type == "co_occurrence"
        assert e.source_type == "signal" and e.target_type == "signal"
    # quantum+chip 共现 2 篇 → 权重 2 的边存在
    sig_by_kw = {s.keywords[0]: s.signal_id for s in signals}
    if "quantum" in sig_by_kw and "chip" in sig_by_kw:
        pair = next(
            (e for e in edges
             if {e.source_id, e.target_id} == {sig_by_kw["quantum"], sig_by_kw["chip"]}),
            None,
        )
        assert pair is not None and pair.weight == 2.0


@pytest.mark.asyncio
@patch(f"{_WS_MODULE}.AdaptiveThreshold")
async def test_extract_multisource_evidence_latest_and_qualified(mock_adaptive_cls):
    """审查 M8:两源同词 → 证据取时间戳最新,doc_id 源限定不混淆。"""
    mock_adaptive_cls.return_value.compute = AsyncMock(return_value=0.0)
    docs = [
        CorpusDoc("science", "science:1", "quantum old", date(2026, 1, 5), ["S机构"]),
        CorpusDoc("patent", "patent:1", "quantum new", date(2026, 3, 5), ["P机构"]),
        CorpusDoc("market", "market:1", "quantum newest", date(2026, 3, 25), ["M机构"]),
    ]
    fake_db, _ = _fake_db()
    ext = WeakSignalExtractor(corpus_loader=_fake_loader(docs), db_connection_id=4)
    signals = await ext.extract(
        db=fake_db, domain=None,
        period_from=date(2026, 1, 1), period_to=date(2026, 3, 31),
    )
    q = next(s for s in signals if "quantum" in s.keywords)
    # 证据按时间戳降序,最新在前
    assert q.evidence_doc_ids[0] == "market:1"
    assert "patent:1" in q.evidence_doc_ids


@pytest.mark.asyncio
@patch(f"{_WS_MODULE}.AdaptiveThreshold")
async def test_extract_rerun_same_period_no_unique_violation(mock_adaptive_cls):
    """审查 H3:窗口重叠重扫同词 → 先删后插,不再撞 signal_id unique。"""
    mock_adaptive_cls.return_value.compute = AsyncMock(return_value=0.0)
    docs = _docs_with_rising_term()
    loader = _fake_loader(docs)
    ext = WeakSignalExtractor(corpus_loader=loader, db_connection_id=4)
    fake_db1, _ = _fake_db()
    fake_db2, _ = _fake_db()
    await ext.extract(db=fake_db1, domain=None,
                      period_from=date(2026, 1, 1), period_to=date(2026, 3, 31))
    # 第二轮同期重扫:execute 被调用(select 旧 id + delete),不抛异常即通过
    await ext.extract(db=fake_db2, domain=None,
                      period_from=date(2026, 2, 1), period_to=date(2026, 3, 31))
    assert fake_db2.execute.await_count >= 1
