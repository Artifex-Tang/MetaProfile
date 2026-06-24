from unittest.mock import patch

import pytest

from metaprofile.ingest_ods.services.extractor import Extractor


def _fake_rows():
    # company_basic_info 真实表无 id 列(PK=company_id);此处 id 仅模拟其他列,
    # keyset/源 id 都走 company_id(见 extractor.KEY_COL)。
    return [
        {"id": 100, "company_id": 1000, "company_name": "甲公司", "usc_code": "U1",
         "company_enname": None, "category_name": "IT", "province": "HUN",
         "estiblish_time": "2010-01-01", "business_scope": "x", "features": {}},
        {"id": 200, "company_id": 2000, "company_name": "乙公司", "usc_code": "U2",
         "company_enname": None, "category_name": "IT", "province": "BJ",
         "estiblish_time": "2011-01-01", "business_scope": "y", "features": {}},
    ]


@pytest.mark.asyncio
async def test_extract_batch_returns_staging_dicts() -> None:
    ext = Extractor()
    with patch("metaprofile.ingest_ods.services.extractor._fetch_rows", return_value=_fake_rows()):
        rows = await ext.extract_batch(
            dsn={"host": "h", "port": 9030, "user": "u", "password": "p",
                 "database": "ods_zbzx", "charset": "utf8mb4"},
            table="ods_company_basic_info",
            last_id=50,
            batch_size=1000,
        )
    assert len(rows) == 2
    assert rows[0]["profile_type"] == "org"
    # KEY_COL: company 表用 company_id 做 keyset/source_id(非 id)
    assert rows[0]["source_id"] == "1000"
    assert rows[0]["entity_key"]["company_id"] == 1000
    assert rows[0]["last_id"] == 2000
    assert rows[1]["source_id"] == "2000"
    assert rows[0]["last_id"] == 2000  # batch 推进游标 = 最大 company_id


@pytest.mark.asyncio
async def test_extract_batch_empty() -> None:
    ext = Extractor()
    with patch("metaprofile.ingest_ods.services.extractor._fetch_rows", return_value=[]):
        rows = await ext.extract_batch({"host": "h"}, "ods_company_basic_info", 0, 1000)
    assert rows == []


# --- watermark 校验:垃圾值("0"/"null"/malformed)会让 update_time > '0' 命中全表,
#     增量过滤失效变全表扫(大表卡死)。须在 SQL 边界前置归 None(走 id-keyset 全量分页)。


@pytest.mark.asyncio
async def test_extract_batch_drops_garbage_watermark() -> None:
    """watermark='0' 不可解析为 datetime → 传给 _fetch_rows 时归 None。"""
    ext = Extractor()
    with patch("metaprofile.ingest_ods.services.extractor._fetch_rows", return_value=[]) as m:
        await ext.extract_batch({"host": "h"}, "ods_company_basic_info", 0, 1000, watermark="0")
    assert m.call_args.args[4] is None  # _fetch_rows 第5参 watermark


@pytest.mark.asyncio
async def test_extract_batch_keeps_valid_watermark() -> None:
    """watermark 为合法 ISO datetime → 原样传给 _fetch_rows。"""
    ext = Extractor()
    wm = "2024-01-01T10:00:00+00:00"
    with patch("metaprofile.ingest_ods.services.extractor._fetch_rows", return_value=[]) as m:
        await ext.extract_batch({"host": "h"}, "ods_company_basic_info", 0, 1000, watermark=wm)
    assert m.call_args.args[4] == wm


@pytest.mark.asyncio
@pytest.mark.parametrize("garbage", ["0", "null", "not-a-date", "", None, 0])
async def test_extract_batch_drops_various_garbage(garbage) -> None:
    """各类垃圾/falsy watermark 一律归 None。"""
    ext = Extractor()
    with patch("metaprofile.ingest_ods.services.extractor._fetch_rows", return_value=[]) as m:
        await ext.extract_batch({"host": "h"}, "ods_company_basic_info", 0, 1000, watermark=garbage)
    assert m.call_args.args[4] is None


# --- _TECH_TABLES(专利/论文)spec-pure 降为 evidence,apply_mapping 返回 None。
#     但 extractor 仍须 EMIT 原始行(profile_type=tech + raw_payload),
#     否则 orchestrator `if not rows: break` → _tech_concept_stage 永不触发
#     → ipc:/concept:/evidence 全丢(e2e 实测"导入 0 条")。


@pytest.mark.asyncio
async def test_extract_batch_emits_unmapped_tech_table_rows() -> None:
    """_TECH_TABLES 表虽 unmapped,仍须 emit 原始行供 tech_concept_stage 消费。"""
    ext = Extractor()
    rows_in = [
        {"id": 10, "title": "一种质谱法装置", "abstract": "ab",
         "ipc_type": "G01N27/62", "Patent_number": "P10"},
    ]
    with patch("metaprofile.ingest_ods.services.extractor._fetch_rows", return_value=rows_in):
        rows = await ext.extract_batch(
            dsn={"host": "h"}, table="ods_invention_patent_cn",
            last_id=0, batch_size=1000,
        )
    assert len(rows) == 1
    r = rows[0]
    assert r["profile_type"] == "tech"
    assert r["source_table"] == "ods_invention_patent_cn"
    assert r["source_id"] == "10"
    assert r["last_id"] == 10
    # tech_concept_stage 读 raw_payload 的 title/abstract/ipc_type
    payload = r["raw_payload"]
    assert payload["title"] == "一种质谱法装置"
    assert payload["ipc_type"] == "G01N27/62"
