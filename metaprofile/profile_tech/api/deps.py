"""依赖注入：FastAPI Depends 的工厂函数。"""
from __future__ import annotations

from functools import lru_cache

from metaprofile.profile_tech.services.tech_enrichment_service import (
    TechEnrichmentService,
)
from metaprofile.profile_tech.services.tech_profile_service import TechProfileService
from metaprofile.profile_tech.services.tech_query_service import TechQueryService
from metaprofile.profile_tech.services.tech_relation_service import TechRelationService
from metaprofile.profile_tech.services.tech_stats_service import TechStatsService


@lru_cache
def get_query_service() -> TechQueryService:
    return TechQueryService()


@lru_cache
def get_profile_service() -> TechProfileService:
    return TechProfileService()


@lru_cache
def get_relation_service() -> TechRelationService:
    return TechRelationService()


@lru_cache
def get_stats_service() -> TechStatsService:
    return TechStatsService()


@lru_cache
def get_enrichment_service() -> TechEnrichmentService:
    return TechEnrichmentService()
