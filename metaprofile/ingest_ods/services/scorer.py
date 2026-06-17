"""阶段④ 真实性 + 时效性 LLM 评分。"""
from __future__ import annotations

import json
from datetime import date

import structlog

from metaprofile.ingest_ods.llm.prompts import SCORE_SYSTEM_PROMPT, ScoreOutput
from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)


def _latest_as_of(source_rows: list[dict]) -> date | None:
    best: date | None = None
    for r in source_rows:
        rp = r.get("raw_payload", {}) if isinstance(r, dict) else {}
        for k in ("update_time", "event_time"):
            v = rp.get(k)
            if not v:
                continue
            try:
                d = date.fromisoformat(str(v)[:10])
            except Exception:
                continue
            if best is None or d > best:
                best = d
    return best


class Scorer:
    def __init__(self, llm) -> None:
        self._llm = llm

    async def score(self, profile_type: str, attrs: dict,
                    source_rows: list[dict]) -> dict:
        data_as_of = _latest_as_of(source_rows)
        prompt = (f"实体类型：{profile_type}\n属性：{json.dumps(attrs, ensure_ascii=False)}\n"
                  f"最新源时间：{data_as_of}\n评判真实性与时效性。")
        try:
            resp = await self._llm.complete(
                model=settings.llm.generation_model,
                messages=[{"role": "system", "content": SCORE_SYSTEM_PROMPT},
                          {"role": "user", "content": prompt}],
                temperature=0.0, caller="ods_ingest_score",
            )
            out = ScoreOutput(**json.loads(resp.content.strip()))
            return {"veracity_score": out.veracity,
                    "timeliness_score": out.timeliness, "data_as_of": data_as_of}
        except Exception as exc:  # noqa: BLE001
            logger.warning("scorer_failed", error=str(exc))
            return {"veracity_score": 0.0, "timeliness_score": 0.0, "data_as_of": data_as_of}
