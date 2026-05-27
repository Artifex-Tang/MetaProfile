"""依赖注入：FastAPI Depends 的工厂函数。"""
from __future__ import annotations

from functools import lru_cache

from metaprofile.profile_person.services.person_enrichment_service import (
    PersonEnrichmentService,
)
from metaprofile.profile_person.services.person_profile_service import PersonProfileService
from metaprofile.profile_person.services.person_query_service import PersonQueryService
from metaprofile.profile_person.services.person_relation_service import PersonRelationService
from metaprofile.profile_person.services.person_stats_service import PersonStatsService


@lru_cache
def get_query_service() -> PersonQueryService:
    return PersonQueryService()


@lru_cache
def get_profile_service() -> PersonProfileService:
    return PersonProfileService()


@lru_cache
def get_relation_service() -> PersonRelationService:
    return PersonRelationService()


@lru_cache
def get_stats_service() -> PersonStatsService:
    return PersonStatsService()


@lru_cache
def get_enrichment_service() -> PersonEnrichmentService:
    return PersonEnrichmentService()
