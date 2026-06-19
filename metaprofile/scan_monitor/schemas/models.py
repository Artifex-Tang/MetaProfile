"""扫描监测 API 模型。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class FrontierTechItem(_Base):
    id: int
    scan_task_id: str
    tech_id: str | None
    tech_name: str
    tech_domain: list[str]
    period_from: date
    period_to: date
    burst_score: float
    patent_score: float
    citation_score: float
    invest_score: float
    policy_score: float
    fusion_score: float
    llm_validated: bool
    llm_verdict: str | None
    trl_level: int | None
    status: str


class FrontierTechList(_Base):
    items: list[FrontierTechItem]
    total: int


class AlertItem(_Base):
    id: int
    tech_name: str
    alert_type: str
    severity: str
    message: str
    fired_at: datetime
    is_read: bool


class AlertList(_Base):
    items: list[AlertItem]
    total: int


class ScanTaskResponse(_Base):
    task_id: str
    period_from: date
    period_to: date
    status: str = "queued"


class FrontierVerifyRequest(_Base):
    """人工验证前沿技术：validated（确认）/ rejected（排除）。"""

    status: Literal["validated", "rejected"]
