"""机构画像 API 请求模型。"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from metaprofile.shared.schemas.entity_org import OrgProfile


class _Req(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SearchRequest(_Req):
    """机构画像多条件搜索。"""

    keyword: str | None = Field(default=None, description="标题/简介关键词")
    org_domain: list[str] | None = None
    invention_date_from: date | None = None
    invention_date_to: date | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class SemanticSearchRequest(_Req):
    """语义搜索（基于 Embedding）。"""

    query: str = Field(..., min_length=1)
    top_k: int = Field(default=20, ge=1, le=100)
    org_domain_filter: list[str] | None = None


class BatchQueryRequest(_Req):
    org_ids: list[str] = Field(..., min_length=1, max_length=100)


class UpdateOrgProfileRequest(_Req):
    """字段级更新：所有字段可选，仅更新非 None 字段。"""

    org_name_cn: str | None = None
    org_name_en: str | None = None
    org_summary: str | None = None
    dev_goal: str | None = None
    key_points: list[str] | None = None
    current_status: str | None = None
    trend: str | None = None
    invention_date: date | None = None
    application_date: date | None = None
    org_advantages: str | None = None
    autonomy_capability: str | None = None
    operator: str = Field(..., description="操作者标识，用于审计日志")
    reason: str | None = Field(default=None, description="本次更新原因")


class BulkImportRequest(_Req):
    """批量导入。"""

    profiles: list[OrgProfile] = Field(..., min_length=1, max_length=1000)
    overwrite: bool = Field(default=False, description="是否覆盖已有同 ID 画像")


class RelationPathRequest(_Req):
    from_id: str
    to_id: str
    max_depth: int = Field(default=4, ge=1, le=6)
