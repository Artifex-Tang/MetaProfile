from unittest.mock import patch

import pytest

from metaprofile.ingest_ods.services.extractor import Extractor


def _fake_rows():
    return [
        {"id": 100, "company_id": 1, "company_name": "甲公司", "usc_code": "U1",
         "company_enname": None, "category_name": "IT", "province": "HUN",
         "estiblish_time": "2010-01-01", "business_scope": "x", "features": {}},
        {"id": 200, "company_id": 2, "company_name": "乙公司", "usc_code": "U2",
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
    assert rows[0]["source_id"] == "100"
    assert rows[0]["entity_key"]["company_id"] == 1
    assert rows[0]["last_id"] == 200
    assert rows[1]["source_id"] == "200"
    assert rows[0]["last_id"] == 200  # batch 的推进游标 = 最大 id


@pytest.mark.asyncio
async def test_extract_batch_empty() -> None:
    ext = Extractor()
    with patch("metaprofile.ingest_ods.services.extractor._fetch_rows", return_value=[]):
        rows = await ext.extract_batch({"host": "h"}, "ods_company_basic_info", 0, 1000)
    assert rows == []
