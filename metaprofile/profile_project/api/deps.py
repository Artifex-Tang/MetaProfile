"""依赖注入：FastAPI Depends 的工厂函数。"""
from __future__ import annotations

from functools import lru_cache

from metaprofile.profile_project.services.project_enrichment_service import (
    ProjectEnrichmentService,
)
from metaprofile.profile_project.services.project_profile_service import ProjectProfileService
from metaprofile.profile_project.services.project_query_service import ProjectQueryService
from metaprofile.profile_project.services.project_relation_service import ProjectRelationService
from metaprofile.profile_project.services.project_stats_service import ProjectStatsService


@lru_cache
def get_query_service() -> ProjectQueryService:
    return ProjectQueryService()


@lru_cache
def get_profile_service() -> ProjectProfileService:
    return ProjectProfileService()


@lru_cache
def get_relation_service() -> ProjectRelationService:
    return ProjectRelationService()


@lru_cache
def get_stats_service() -> ProjectStatsService:
    return ProjectStatsService()


@lru_cache
def get_enrichment_service() -> ProjectEnrichmentService:
    return ProjectEnrichmentService()
