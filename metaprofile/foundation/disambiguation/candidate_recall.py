"""
基于 Embedding 的消歧候选召回。

策略：
1. 待消歧实体的 name + summary 编码为向量
2. ES kNN 检索 Top K 相似实体
3. 按余弦相似度阈值分流：
   - >= 0.95：直接合并（不进 LLM）
   - 0.70~0.95：进 LLM 精判
   - <  0.70：丢弃
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from metaprofile.shared.config.settings import settings
from metaprofile.shared.llm.embedding import EmbeddingClient
from metaprofile.shared.schemas.base import EntityType

# 各实体类型的"主名称"字段名（用于显示候选名称）
_NAME_FIELD: dict[EntityType, str] = {
    EntityType.TECH: "tech_name_cn",
    EntityType.ORG: "org_name_cn",
    EntityType.PERSON: "name_cn",
    EntityType.PROJECT: "project_name",
}


@dataclass
class CandidatePair:
    candidate_id: str
    candidate_name: str
    similarity: float
    raw_data: dict[str, Any]   # 完整文档，供 LLM 精判使用


class CandidateRecaller:
    """消歧候选召回器。"""

    AUTO_MERGE_THRESHOLD = settings.thresholds.disambig_auto_merge
    LLM_JUDGE_MIN_THRESHOLD = settings.thresholds.disambig_llm_judge_min

    def __init__(self, embedding_client: EmbeddingClient, es_repo: Any) -> None:
        self._embedding = embedding_client
        self._es = es_repo

    async def recall(
        self,
        *,
        entity_type: EntityType,
        query_text: str,
        top_k: int = 20,
    ) -> tuple[list[CandidatePair], list[CandidatePair], list[CandidatePair]]:
        """
        Returns:
            (auto_merge, need_llm_judge, discard) 三组候选
        """
        vector = await self._embedding.embed_one(query_text)
        # FoundationESRepo.knn_search 返回已展平的 doc dict（含 _score/_id）
        hits: list[dict[str, Any]] = await self._es.knn_search(
            index_alias=f"{settings.es.profile_index_prefix}{entity_type.value.lower()}_profile",
            vector=vector,
            top_k=top_k,
        )

        name_field = _NAME_FIELD.get(entity_type, "name_cn")

        auto_merge: list[CandidatePair] = []
        need_judge: list[CandidatePair] = []
        discard: list[CandidatePair] = []

        for hit in hits:
            similarity = float(hit.get("_score", 0.0))
            pair = CandidatePair(
                candidate_id=hit.get("entity_id", hit.get("_id", "")),
                candidate_name=hit.get(name_field, ""),
                similarity=similarity,
                raw_data={k: v for k, v in hit.items() if not k.startswith("_")},
            )
            if similarity >= self.AUTO_MERGE_THRESHOLD:
                auto_merge.append(pair)
            elif similarity >= self.LLM_JUDGE_MIN_THRESHOLD:
                need_judge.append(pair)
            else:
                discard.append(pair)

        return auto_merge, need_judge, discard
