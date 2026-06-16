"""选题服务 API 模型。"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class TopicItem(_Base):
    id: int
    topic_id: str
    title: str
    summary: str
    period: str | None
    related_tech_ids: list[str]
    score_hot: float
    score_policy: float
    score_impact: float
    score_dedup: float
    score_llm_gen: float
    review_novelty: float
    review_importance: float
    review_feasibility: float
    review_expression: float
    final_score: float
    status: str


class TopicList(_Base):
    items: list[TopicItem]
    total: int


class TopicDetail(TopicItem):
    related_org_ids: list[str]
    related_project_ids: list[str]
    related_policy_refs: list[str]
    review_evidence: str | None
    # 解析后的名称（便于展示，避免前端只看到 ID）
    related_tech_names: list[str] = []
    related_org_names: list[str] = []
    related_project_names: list[str] = []


class GenerateTaskResponse(_Base):
    task_id: str
    target_count: int
    period_from: str | None
    period_to: str | None
    status: str = "queued"


class FeedbackResponse(_Base):
    topic_id: str
    status: str = "recorded"
