"""L2: 从论文/专利 title+abstract 用 LLM 抽取具体技术术语。

输出含中文规范名 name_cn:英文源术语在抽取层即归一为中文,
使下游(bge-large-zh 聚类 / jieba 弱信号)整条中文链路不被英文术语污染。
英文原文 term 保留(→ cluster_terms / tech_aliases)。
"""
from __future__ import annotations

import json

from pydantic import TypeAdapter

from metaprofile.ingest_ods.llm.prompts import MinedTechTerm, TECH_MINER_SYSTEM_PROMPT
from metaprofile.shared.config.settings import settings

# 摘要截断:防止超长摘要撑爆上下文 / 拉高 token 成本。
_MAX_CHARS = 3000

_TermsAdapter: TypeAdapter[list[MinedTechTerm]] = TypeAdapter(list[MinedTechTerm])


class TechConceptMiner:
    """L2 技术术语挖掘器。无状态:依赖注入的 LLM 网关承担重试/计量/落库。"""

    def __init__(self, llm) -> None:
        self._llm = llm

    async def mine(self, *, title: str, abstract: str | None = None) -> list[MinedTechTerm]:
        # 空 title 视为无信号:不调用 LLM,直接返回空。
        if not (title or "").strip():
            return []
        text = f"标题:{title}\n摘要:{(abstract or '')[:_MAX_CHARS]}"
        resp = await self._llm.complete(
            model=settings.llm.extraction_model,
            messages=[
                {"role": "system", "content": TECH_MINER_SYSTEM_PROMPT},
                {"role": "user", "content": text},
            ],
            temperature=0.0,
            caller="tech_concept_mine",
        )
        try:
            data = json.loads(resp.content.strip())
            return _TermsAdapter.validate_python(data.get("terms", []))
        except Exception:
            # LLM 偶发格式漂移不应中断管线:降级为空,由上游计入该条无 tech。
            return []
