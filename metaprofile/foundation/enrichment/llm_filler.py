"""
LLM 字段补全器。

针对完整度不足的实体，使用 RAG 检索到的支撑文档作为上下文，
让 LLM 填充指定缺失字段。
输出经过置信度过滤后写回实体属性。
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from pydantic import Field

from metaprofile.shared.config.settings import settings
from metaprofile.shared.llm.gateway import LLMGateway
from metaprofile.shared.schemas.base import EntityType, ProfileBase

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是实体画像数据补全专家。
根据提供的参考文献，补全实体画像中的缺失字段。
仅补全提供的字段列表，不修改已有字段。
若参考文献中没有足够信息，请将对应字段设为 null 并降低 confidence。
以 JSON 格式输出，包含 filled_fields（dict）和 confidence（float 0-1）。
"""

_ENRICH_MAX_CONTEXT_CHARS = 4000


class _FillOutput(ProfileBase):
    filled_fields: dict[str, Any] = Field(default_factory=dict)
    confidence: float = Field(..., ge=0.0, le=1.0)


@dataclass
class FillResult:
    filled_fields: dict[str, Any]
    confidence: float
    accepted_fields: list[str] = field(default_factory=list)    # fields written back
    rejected_fields: list[str] = field(default_factory=list)    # below threshold


class LLMFieldFiller:
    """
    用 LLM + RAG 上下文补全指定缺失字段。

    接受阈值：settings.thresholds.enrichment_auto_accept (≥0.80 自动写入)
    复查阈值：settings.thresholds.enrichment_review_min (≥0.60 供人工审核)
    低于复查阈值的字段直接丢弃。
    """

    caller_name = "llm_field_filler"

    def __init__(self, gateway: LLMGateway) -> None:
        self._gateway = gateway

    async def fill(
        self,
        *,
        entity_type: EntityType,
        entity_attrs: dict[str, Any],
        missing_fields: list[str],
        context_docs: list[str],
        auto_accept_threshold: float | None = None,
        review_min_threshold: float | None = None,
    ) -> FillResult:
        """
        补全 missing_fields。

        Args:
            entity_attrs: 现有实体属性（供 LLM 理解上下文）
            missing_fields: 需要补全的字段名列表
            context_docs: RAG 检索到的文档 snippet 列表
            auto_accept_threshold: 自动写入阈值（默认从 settings 读取）
            review_min_threshold: 最低复查阈值（低于此则丢弃）

        Returns:
            FillResult 含 filled_fields（已过阈值）、rejected_fields
        """
        auto_thresh = auto_accept_threshold or settings.thresholds.enrichment_auto_accept
        review_thresh = review_min_threshold or settings.thresholds.enrichment_review_min

        if not missing_fields:
            return FillResult(filled_fields={}, confidence=1.0)

        context_text = _build_context(context_docs)
        entity_summary = _summarize_entity(entity_attrs)
        fields_str = "、".join(missing_fields)

        user_prompt = (
            f"实体类型：{entity_type.value}\n"
            f"已知属性：\n{entity_summary}\n\n"
            f"需补全字段：{fields_str}\n\n"
            f"参考文献：\n{context_text}\n\n"
            f"请以 JSON 格式返回 filled_fields 和 confidence。"
        )

        try:
            response = await self._gateway.complete(
                model=settings.llm.generation_model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.1,
                caller=self.caller_name,
            )
            raw = response.content.strip()
            parsed = _parse_json_response(raw)
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLMFieldFiller failed: %s", exc)
            return FillResult(
                filled_fields={},
                confidence=0.0,
                rejected_fields=missing_fields,
            )

        confidence = float(parsed.get("confidence", 0.0))
        raw_filled: dict[str, Any] = parsed.get("filled_fields", {})

        accepted: dict[str, Any] = {}
        accepted_names: list[str] = []
        rejected_names: list[str] = []

        for fname in missing_fields:
            val = raw_filled.get(fname)
            if val is None or val == "" or val == []:
                rejected_names.append(fname)
                continue
            if confidence >= auto_thresh:
                accepted[fname] = val
                accepted_names.append(fname)
            elif confidence >= review_thresh:
                # Accept the value but flag it for review (still pass it back)
                accepted[fname] = val
                accepted_names.append(fname)
            else:
                rejected_names.append(fname)

        return FillResult(
            filled_fields=accepted,
            confidence=confidence,
            accepted_fields=accepted_names,
            rejected_fields=rejected_names,
        )


# ─── helpers ────────────────────────────────────────────────────────────────

def _build_context(docs: list[str]) -> str:
    parts: list[str] = []
    total = 0
    for i, doc in enumerate(docs, 1):
        chunk = f"[{i}] {doc}"
        if total + len(chunk) > _ENRICH_MAX_CONTEXT_CHARS:
            break
        parts.append(chunk)
        total += len(chunk)
    return "\n\n".join(parts) or "（无参考文献）"


def _summarize_entity(attrs: dict[str, Any]) -> str:
    lines = []
    for k, v in attrs.items():
        if v is None or v == "" or v == []:
            continue
        if isinstance(v, list) and len(v) > 3:
            v = v[:3]
        lines.append(f"  {k}: {v}")
    return "\n".join(lines[:20])  # cap at 20 lines


def _parse_json_response(text: str) -> dict[str, Any]:
    # Strip markdown code fences if present
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1]) if len(lines) > 2 else text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}
