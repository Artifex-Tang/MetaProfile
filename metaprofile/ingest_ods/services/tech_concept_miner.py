"""L2: 从论文/专利 title+abstract 用 LLM 抽取具体技术术语。

输出含中文规范名 name_cn:英文源术语在抽取层即归一为中文,
使下游(bge-large-zh 聚类 / jieba 弱信号)整条中文链路不被英文术语污染。
英文原文 term 保留(→ cluster_terms / tech_aliases)。
"""
from __future__ import annotations

import json

import structlog
from pydantic import TypeAdapter

from metaprofile.ingest_ods.llm.prompts import MinedTechTerm, TECH_MINER_SYSTEM_PROMPT
from metaprofile.shared.config.settings import settings

logger = structlog.get_logger(__name__)

# 摘要截断:防止超长摘要撑爆上下文 / 拉高 token 成本。
_MAX_CHARS = 3000

_TermsAdapter: TypeAdapter[list[MinedTechTerm]] = TypeAdapter(list[MinedTechTerm])


def _extract_terms_json(content: str) -> list[dict]:
    """从 LLM 返回中抽取 terms 列表,容忍 markdown 围栏 / prose 包装。

    glm-4.7 实测会把 JSON 包进 ```json ... ```;裸 json.loads 见到反引号即失败。
    解析顺序:
      1. 去掉首尾 ``` / ```json 围栏;
      2. 若去围栏后仍不以 `{` 开头,退回对原始 content 取首个 `{` 到末个 `}` 的切片;
      3. json.loads,返回 data["terms"]。
    硬解析失败抛异常,交由调用方 catch + 记 warning。
    """
    if content is None:
        raise ValueError("empty LLM content")
    raw = content.strip()

    # 1. 剥离 markdown 围栏(首 ```... 行 + 末 ```)。
    stripped = raw
    if stripped.startswith("```"):
        # 去掉开头的 ```json / ``` 行
        first_nl = stripped.find("\n")
        if first_nl != -1:
            stripped = stripped[first_nl + 1 :]
        else:
            stripped = stripped.lstrip("`jsonJSON \t")
        stripped = stripped.strip()
        # 去掉结尾独立的 ```
        if stripped.endswith("```"):
            stripped = stripped[: -3].strip()

    # 2. 仍不是 JSON 对象开头 → prose 包装,取 {…} 切片兜底。
    if not stripped.startswith("{"):
        first = raw.find("{")
        last = raw.rfind("}")
        if first != -1 and last != -1 and last > first:
            stripped = raw[first : last + 1]

    data = json.loads(stripped)
    return data.get("terms", [])


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
            terms_raw = _extract_terms_json(resp.content)
            return _TermsAdapter.validate_python(terms_raw)
        except Exception as exc:
            # LLM 偶发格式漂移不应中断管线:降级为空,由上游计入该条无 tech。
            # M4: 不再静默,记 warning 让解析失败可观测(raw_head 截断防爆日志)。
            logger.warning(
                "tech_miner_parse_failed",
                error=str(exc),
                raw_head=(resp.content or "")[:120],
            )
            return []
