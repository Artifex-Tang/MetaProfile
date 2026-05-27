"""集成测试：topic_selection 域模型 + 反馈闭环（需真实 PostgreSQL）。"""
from __future__ import annotations

import pytest

from metaprofile.topic_selection.domain.orm_models import TopicCandidateORM, TopicFeedbackORM
from metaprofile.topic_selection.services.feedback_loop import FeedbackLoopService
from metaprofile.topic_selection.services.score_fusion import ScoreFusion, TopicCandidate

pytestmark = pytest.mark.asyncio


def _make_topic(topic_id: str = "TOPIC_INT_001") -> TopicCandidateORM:
    return TopicCandidateORM(
        topic_id=topic_id,
        title="量子计算在密码学中的应用前景",
        summary="探讨后量子密码算法与量子计算机威胁",
        period="2026Q2",
        related_tech_ids=["TECH_001"],
        related_org_ids=[],
        related_project_ids=[],
        related_policy_refs=[],
        score_hot=0.8,
        score_policy=0.6,
        score_impact=0.7,
        score_dedup=0.9,
        score_llm_gen=0.75,
        review_novelty=0.8,
        review_importance=0.9,
        review_feasibility=0.7,
        review_expression=0.85,
        review_evidence="技术新颖，政策高度关注",
        final_score=0.78,
    )


async def test_create_topic_candidate(db_session):
    orm = _make_topic()
    db_session.add(orm)
    await db_session.flush()
    assert orm.id is not None
    assert orm.topic_id == "TOPIC_INT_001"


async def test_feedback_accept(db_session):
    orm = _make_topic("TOPIC_INT_002")
    db_session.add(orm)
    await db_session.flush()

    svc = FeedbackLoopService(db_session)
    feedback = await svc.record(
        topic_id="TOPIC_INT_002",
        rating="accept",
        score=4,
        comments="选题方向很好",
        operator="alice",
    )
    assert feedback.rating == "accept"
    assert feedback.score == 4


async def test_feedback_updates_topic_status(db_session):
    orm = _make_topic("TOPIC_INT_003")
    db_session.add(orm)
    await db_session.flush()

    svc = FeedbackLoopService(db_session)
    await svc.record(
        topic_id="TOPIC_INT_003",
        rating="reject",
        score=2,
        comments="范围太广",
        operator="bob",
    )
    # 刷新对象，验证 status 已更新
    await db_session.refresh(orm)
    assert orm.status == "rejected"


async def test_feedback_accept_updates_status_to_accepted(db_session):
    orm = _make_topic("TOPIC_INT_004")
    db_session.add(orm)
    await db_session.flush()

    svc = FeedbackLoopService(db_session)
    await svc.record(
        topic_id="TOPIC_INT_004",
        rating="accept",
        score=5,
        comments=None,
        operator="carol",
    )
    await db_session.refresh(orm)
    assert orm.status == "accepted"


async def test_compute_acceptance_rate_with_data(db_session):
    # 插入 2 accept + 1 reject
    for i, rating in enumerate(["accept", "accept", "reject"]):
        fb = TopicFeedbackORM(
            topic_id=f"TOPIC_INT_RATE_{i}",
            rating=rating,
            score=3,
            operator="tester",
        )
        db_session.add(fb)
    await db_session.flush()

    svc = FeedbackLoopService(db_session)
    rate = await svc.compute_acceptance_rate()
    # 2/3 ≈ 0.667
    assert abs(rate - 2 / 3) < 0.01


async def test_score_fusion_with_real_candidate():
    fusion = ScoreFusion()
    cand = TopicCandidate(
        topic_id="TOPIC_FUSE_001",
        title="测试选题",
        summary="测试摘要",
        related_tech_ids=[],
        related_org_ids=[],
        related_project_ids=[],
        related_policy_refs=[],
        score_hot=0.8,
        score_policy=0.6,
        score_impact=0.7,
        score_dedup=0.9,
        score_llm_gen=0.75,
        review_novelty=0.8,
        review_importance=0.9,
        review_feasibility=0.7,
        review_expression=0.85,
        review_evidence="",
        final_score=0.0,
    )
    score = fusion.fuse(cand)
    assert 0.0 <= score <= 1.0
    # 策略分 ≈ 0.25*0.8+0.20*0.6+0.20*0.7+0.15*0.9+0.20*0.75=0.735
    # 评审分 ≈ 0.30*0.8+0.30*0.9+0.20*0.7+0.20*0.85=0.825
    # final ≈ 0.6*0.735+0.4*0.825=0.771
    assert abs(score - 0.771) < 0.01
