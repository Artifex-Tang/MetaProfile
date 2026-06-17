from datetime import date
from unittest.mock import AsyncMock

import pytest

from metaprofile.ingest_ods.services.scorer import Scorer


class _Resp:
    def __init__(self, c: str) -> None:
        self.content = c


@pytest.mark.asyncio
async def test_score_parses_and_sets_fields() -> None:
    llm = AsyncMock()
    llm.complete = AsyncMock(return_value=_Resp('{"veracity":0.8,"timeliness":0.6,"reason":"ok"}'))
    sc = Scorer(llm=llm)
    result = await sc.score(
        profile_type="org",
        attrs={"name_cn": "甲公司", "summary": "x"},
        source_rows=[{"raw_payload": {"update_time": "2026-06-01"}}],
    )
    assert result["veracity_score"] == 0.8
    assert result["timeliness_score"] == 0.6
    assert result["data_as_of"] == date(2026, 6, 1)


@pytest.mark.asyncio
async def test_score_llm_failure_defaults_zero() -> None:
    llm = AsyncMock()
    llm.complete = AsyncMock(side_effect=RuntimeError("boom"))
    sc = Scorer(llm=llm)
    result = await sc.score("org", {"name_cn": "x"}, [{}])
    assert result["veracity_score"] == 0.0
