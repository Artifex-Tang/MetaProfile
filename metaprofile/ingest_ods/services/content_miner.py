"""阶段② 内容→表：附件 clean_content LLM 抽实体 + 关系三元组。"""
from __future__ import annotations

import json
from datetime import datetime, timezone

import structlog
from pydantic import TypeAdapter

from metaprofile.ingest_ods.llm.prompts import (
    MINE_SYSTEM_PROMPT, MinedEntity, MinedRelation, map_predicate,
)
from metaprofile.shared.config.settings import settings
from metaprofile.shared.schemas.base import EntityType, SourceMethod
from metaprofile.shared.schemas.relations import RelationTriple

logger = structlog.get_logger(__name__)

_MAX_CHARS = 4000


def _chunk(text: str) -> list[str]:
    return [text[i:i + _MAX_CHARS] for i in range(0, len(text), _MAX_CHARS)] or [text]


_ENT_TYPES = {"tech": EntityType.TECH, "org": EntityType.ORG,
              "person": EntityType.PERSON, "project": EntityType.PROJECT}


class ContentMiner:
    def __init__(self, llm) -> None:
        self._llm = llm

    async def _extract_chunk(self, text: str) -> tuple[list[MinedEntity], list[MinedRelation]]:
        resp = await self._llm.complete(
            model=settings.llm.extraction_model,
            messages=[{"role": "system", "content": MINE_SYSTEM_PROMPT},
                      {"role": "user", "content": f"正文：\n{text}"}],
            temperature=0.0, caller="ods_ingest_mine",
        )
        try:
            data = json.loads(resp.content.strip())
        except Exception as exc:  # noqa: BLE001
            logger.warning("mine_parse_failed", error=str(exc))
            return [], []
        ents = TypeAdapter(list[MinedEntity]).validate_python(data.get("entities", []))
        rels = TypeAdapter(list[MinedRelation]).validate_python(data.get("relations", []))
        return ents, rels

    async def mine(self, attachments: list[dict]) -> tuple[list[dict], list[RelationTriple]]:
        entities: list[dict] = []
        rels: list[RelationTriple] = []
        now = datetime.now(timezone.utc)
        for att in attachments:
            text = att.get("clean_content")
            if not text:
                continue
            for chunk in _chunk(text):
                mined_ents, mined_rels = await self._extract_chunk(chunk)
                for e in mined_ents:
                    entities.append({"type": e.type, "name": e.name, "attrs": e.attrs,
                                     "veracity_hint": e.veracity_hint, "as_of": e.as_of,
                                     "source_doc_id": str(att.get("original_id"))})
                for r in mined_rels:
                    rel = map_predicate(r.predicate, r.subject_type, r.object_type)
                    if rel is None:
                        continue
                    rels.append(RelationTriple(
                        subject_id=f"name:{r.subject_name}",
                        subject_type=_ENT_TYPES[r.subject_type],
                        subject_name=r.subject_name,
                        relation=rel,
                        object_id=f"name:{r.object_name}",
                        object_type=_ENT_TYPES[r.object_type],
                        object_name=r.object_name,
                        evidence=r.evidence, confidence=r.confidence,
                        source_doc_id=str(att.get("original_id")),
                        method=SourceMethod.LLM_EXTRACT, extracted_at=now,
                    ))
        return entities, rels
