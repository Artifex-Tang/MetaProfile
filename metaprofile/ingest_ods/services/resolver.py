"""阶段③ 实体合并/消歧：强键直接归并，弱键 name 簇 + LLM 判同异。"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from metaprofile.ingest_ods.llm.prompts import DISAMBIG_SYSTEM_PROMPT, DisambigResult
from metaprofile.shared.config.settings import settings

_STRONG_KEYS = {"company_id", "usc_code", "orcid", "email", "doi", "patent_number"}


def _strong_key(entity_key: dict) -> str | None:
    for k in _STRONG_KEYS:
        if entity_key.get(k):
            return f"{k}:{entity_key[k]}"
    return None


def _merge_attrs(base: dict, extra: dict) -> dict:
    out = dict(base)
    for k, v in extra.items():
        if k not in out or out[k] in (None, "", []):
            out[k] = v
    return out


class EntityResolver:
    def __init__(self, llm) -> None:
        self._llm = llm

    async def _disambig(self, a: dict, b: dict) -> bool:
        prompt = (f"实体A：{json.dumps(a, ensure_ascii=False)}\n"
                  f"实体B：{json.dumps(b, ensure_ascii=False)}\n判断是否同一对象。")
        resp = await self._llm.complete(
            model=settings.llm.generation_model,
            messages=[{"role": "system", "content": DISAMBIG_SYSTEM_PROMPT},
                      {"role": "user", "content": prompt}],
            temperature=0.0, caller="ods_ingest_resolve",
        )
        try:
            return bool(DisambigResult(**json.loads(resp.content.strip())).same)
        except Exception:
            return False

    async def resolve(self, rows: list[dict]) -> list[dict]:
        # 1. 强键归并
        by_strong: dict[str, dict] = {}
        weak: list[dict] = []
        for r in rows:
            attrs = r["raw_payload"].get("_attrs", {})
            sk = _strong_key(r["entity_key"])
            base = {"profile_type": r["profile_type"], "entity_key": dict(r["entity_key"]),
                    "attrs": dict(attrs), "source_rows": [r]}
            if sk:
                if sk in by_strong:
                    by_strong[sk]["attrs"] = _merge_attrs(by_strong[sk]["attrs"], attrs)
                    by_strong[sk]["entity_key"].update(r["entity_key"])
                    by_strong[sk]["source_rows"].append(r)
                else:
                    by_strong[sk] = base
            else:
                weak.append(base)

        entities = list(by_strong.values())

        # 2. 弱键：name 归一簇，逐对 LLM 判同异
        clusters: dict[tuple, list[dict]] = defaultdict(list)
        for e in weak:
            name = (e["attrs"].get("name_cn") or e["attrs"].get("tech_name_cn") or "").strip()
            clusters[(e["profile_type"], name)].append(e)
        for (ptype, name), group in clusters.items():
            if not name:
                entities.extend(group)
                continue
            merged = group[0]
            for other in group[1:]:
                same = await self._disambig(merged["attrs"], other["attrs"])
                if same:
                    merged["attrs"] = _merge_attrs(merged["attrs"], other["attrs"])
                    merged["source_rows"].extend(other["source_rows"])
                else:
                    entities.append(other)
            entities.append(merged)
        return entities
