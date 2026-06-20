"""新技术发现 API 模型。"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class WeakSignalItem(_Base):
    id: int
    signal_id: str
    keywords: list[str]
    related_tech_ids: list[str]
    related_org_ids: list[str]
    related_person_ids: list[str]
    evidence_doc_ids: list[str] = Field(default_factory=list)
    strength: float
    novelty: float
    coherence: float
    diversity: float = 0.0
    velocity: float = 0.0
    period_from: date
    period_to: date
    domain: str | None
    status: str


class WeakSignalList(_Base):
    items: list[WeakSignalItem]
    total: int


class SignalNetworkNode(_Base):
    entity_id: str
    entity_type: str
    name: str | None = None


class SignalNetworkEdge(_Base):
    source_id: str
    target_id: str
    edge_type: str
    weight: float


class SignalNetwork(_Base):
    signal_id: str
    nodes: list[SignalNetworkNode]
    edges: list[SignalNetworkEdge]


class ScanTaskResponse(_Base):
    task_id: str
    domain: str | None
    status: str = "queued"
