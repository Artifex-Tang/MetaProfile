"""项目画像 API 响应模型。"""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from metaprofile.shared.schemas.entity_project import ProjectProfile


class _Resp(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class ProjectProfileResponse(ProjectProfile):
    """完整项目画像响应（继承自 ProjectProfile）。"""

    # ingest_ods scorer 产出的数据质量评分（output-only，系统计算）
    veracity_score: float = Field(default=0.0, ge=0.0, le=1.0, description="真实性评分")
    timeliness_score: float = Field(default=0.0, ge=0.0, le=1.0, description="时效性评分")
    data_as_of: date | None = Field(default=None, description="数据截止日期")


class ProjectSearchResultItem(_Resp):
    project_id: str
    project_name_cn: str
    project_domain: list[str]
    relevance_score: float | None = None


class ProjectSearchResultList(_Resp):
    items: list[ProjectSearchResultItem]
    total: int


class ChangeRecord(_Resp):
    project_id: str
    field: str
    old_value: Any | None
    new_value: Any | None
    method: str
    operator: str | None
    changed_at: datetime


class ChangeRecordList(_Resp):
    items: list[ChangeRecord]
    total: int


class RelationItem(_Resp):
    relation_type: str
    target_entity_id: str
    target_entity_type: str
    target_name: str | None = None
    confidence: float
    evidence: str | None = None


class RelationList(_Resp):
    items: list[RelationItem]
    total: int


class RelationPathStep(_Resp):
    from_id: str
    relation: str
    to_id: str


class RelationPathResult(_Resp):
    found: bool
    paths: list[list[RelationPathStep]]


class ProjectStatsResponse(_Resp):
    total: int
    new_this_period: int
    updated_this_period: int
    domain_distribution: dict[str, int]
    completeness_histogram: dict[str, int] = Field(
        default_factory=dict,
        description="完整度分布直方图，如 {'0-30': 12, '30-60': 24, ...}",
    )
    llm_contribution_ratio: float
    updated_at: datetime | None


class BulkImportResult(_Resp):
    task_id: str
    accepted_count: int
    submitted_at: datetime


class EnrichmentTaskResponse(_Resp):
    task_id: str
    project_id: str
    current_completeness: float
    status: str
    submitted_at: datetime
