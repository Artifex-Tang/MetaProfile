"""依赖注入：FastAPI Depends 的工厂函数。"""
from __future__ import annotations

from functools import lru_cache

from metaprofile.profile_org.services.org_enrichment_service import OrgEnrichmentService
from metaprofile.profile_org.services.org_profile_service import OrgProfileService
from metaprofile.profile_org.services.org_query_service import OrgQueryService
from metaprofile.profile_org.services.org_relation_service import OrgRelationService
from metaprofile.profile_org.services.org_stats_service import OrgStatsService


@lru_cache
def get_query_service() -> OrgQueryService:
    return OrgQueryService()


@lru_cache
def get_profile_service() -> OrgProfileService:
    return OrgProfileService()


@lru_cache
def get_relation_service() -> OrgRelationService:
    return OrgRelationService()


@lru_cache
def get_stats_service() -> OrgStatsService:
    return OrgStatsService()


@lru_cache
def get_enrichment_service() -> OrgEnrichmentService:
    return OrgEnrichmentService()
