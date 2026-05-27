"""
Elasticsearch Repository（foundation 层封装）。

对 shared.db.ESRepo 做实体语义封装：
- index 命名：{prefix}{entity_type}_profile（如 metaprofile_tech_profile）
- 向量字段统一为 "embedding"
- mapping 模板按实体类型预定义
"""
from __future__ import annotations

from typing import Any

import structlog

from metaprofile.shared.config.settings import settings
from metaprofile.shared.db.elasticsearch import ESRepo
from metaprofile.shared.schemas.base import EntityType

logger = structlog.get_logger(__name__)

# kNN 向量字段 mapping（所有实体通用）
_KNN_FIELD_MAPPING: dict[str, Any] = {
    "type": "dense_vector",
    "dims": settings.es.embedding_dim,
    "index": True,
    "similarity": "cosine",
}

# 每类实体额外的文本字段 mapping
_ENTITY_TEXT_FIELDS: dict[str, dict[str, Any]] = {
    EntityType.TECH: {
        "tech_name_cn": {"type": "text", "analyzer": "ik_max_word"},
        "tech_name_en": {"type": "text", "analyzer": "english"},
        "tech_summary": {"type": "text", "analyzer": "ik_max_word"},
        "current_status": {"type": "text", "analyzer": "ik_max_word"},
        "trend": {"type": "text", "analyzer": "ik_max_word"},
        "tech_domain": {"type": "keyword"},
    },
    EntityType.ORG: {
        "org_name_cn": {"type": "text", "analyzer": "ik_max_word"},
        "org_name_en": {"type": "text", "analyzer": "english"},
        "org_summary": {"type": "text", "analyzer": "ik_max_word"},
        "org_type": {"type": "keyword"},
        "country": {"type": "keyword"},
    },
    EntityType.PERSON: {
        "name_cn": {"type": "text", "analyzer": "ik_max_word"},
        "name_en": {"type": "text", "analyzer": "english"},
        "research_domains": {"type": "keyword"},
        "current_affiliation": {"type": "keyword"},
    },
    EntityType.PROJECT: {
        "project_name": {"type": "text", "analyzer": "ik_max_word"},
        "project_summary": {"type": "text", "analyzer": "ik_max_word"},
        "tech_domains": {"type": "keyword"},
        "status": {"type": "keyword"},
    },
}


class FoundationESRepo:
    """Foundation 层 ES Repository：封装 index 命名与 mapping 管理。"""

    def __init__(self, repo: ESRepo | None = None) -> None:
        self._repo = repo or ESRepo()

    def index_name(self, entity_type: EntityType) -> str:
        return f"{settings.es.profile_index_prefix}{entity_type.value.lower()}_profile"

    async def ensure_entity_index(self, entity_type: EntityType) -> None:
        """确保实体 index 存在，包含向量字段和文本字段。"""
        fields = dict(_ENTITY_TEXT_FIELDS.get(entity_type, {}))
        fields["entity_id"] = {"type": "keyword"}
        fields["entity_type"] = {"type": "keyword"}
        fields["embedding"] = _KNN_FIELD_MAPPING
        fields["confidence"] = {"type": "float"}
        fields["completeness"] = {"type": "float"}
        fields["updated_at"] = {"type": "date"}

        mapping = {"properties": fields}
        es_settings = {
            "number_of_shards": 1,
            "number_of_replicas": 1,
        }
        await self._repo.ensure_index(
            index=self.index_name(entity_type),
            mapping=mapping,
            settings_body=es_settings,
        )

    async def upsert(
        self,
        *,
        index: str,
        doc_id: str,
        body: dict[str, Any],
    ) -> None:
        """兼容 unified_repo 的直接调用签名。"""
        await self._repo.upsert(index=index, doc_id=doc_id, body=body)

    async def upsert_entity(
        self,
        *,
        entity_type: EntityType,
        entity_id: str,
        attributes: dict[str, Any],
        embedding: list[float] | None = None,
    ) -> None:
        """实体语义 upsert（自动决定 index 名）。"""
        body = dict(attributes)
        body["entity_id"] = entity_id
        body["entity_type"] = entity_type.value
        if embedding:
            body["embedding"] = embedding
        await self._repo.upsert(
            index=self.index_name(entity_type),
            doc_id=entity_id,
            body=body,
        )

    async def get_entity(
        self,
        entity_type: EntityType,
        entity_id: str,
    ) -> dict[str, Any] | None:
        return await self._repo.get(index=self.index_name(entity_type), doc_id=entity_id)

    async def search_entities(
        self,
        entity_type: EntityType,
        *,
        query: dict[str, Any],
        size: int = 10,
        from_: int = 0,
    ) -> list[dict[str, Any]]:
        return await self._repo.search(
            index=self.index_name(entity_type),
            query=query,
            size=size,
            from_=from_,
        )

    async def knn_search(
        self,
        *,
        index_alias: str,
        vector: list[float],
        top_k: int = 20,
        num_candidates: int = 100,
        filter_query: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """消歧召回使用。index_alias 由调用方传入。"""
        return await self._repo.knn_search(
            index_alias=index_alias,
            vector=vector,
            top_k=top_k,
            num_candidates=num_candidates,
            filter_query=filter_query,
        )

    async def delete_entity(self, entity_type: EntityType, entity_id: str) -> bool:
        return await self._repo.delete(
            index=self.index_name(entity_type), doc_id=entity_id
        )
