from metaprofile.ingest_ods.domain.mappings import apply_mapping, get_mapping


def test_company_basic_info_to_org() -> None:
    m = get_mapping("ods_company_basic_info")
    assert m is not None
    assert m.profile_type == "org"
    assert "company_id" in m.key_fields

    row = {
        "company_id": 101023784,
        "company_name": "某科技有限公司",
        "company_enname": "Foo Tech",
        "usc_code": "91110000MA001X",
        "category_name": "信息技术",
        "province": "HUN",
        "estiblish_time": "2010-01-01",
        "business_scope": "软件开发",
        "legal_person_name": "张三",
        "reg_capital": "1000万人民币",
    }
    out = apply_mapping("ods_company_basic_info", row)
    assert out["profile_type"] == "org"
    assert out["entity_key"]["company_id"] == 101023784
    assert out["entity_key"]["usc_code"] == "91110000MA001X"
    assert out["attrs"]["name_cn"] == "某科技有限公司"
    assert out["attrs"]["name_en"] == "Foo Tech"
    assert out["attrs"]["tech_domains"] == ["信息技术"]
    assert out["attrs"]["founded_date"] == "2010-01-01"


def test_talent_info_to_person() -> None:
    row = {"id": 1, "full_name": "李四", "education": "博士", "job_title": "研究员",
           "employer": "上海交通大学",
           "features": {"sex": "男", "mail": "a@b.com", "discipline": "计算机",
                        "graduatedUniversity": "清华"}}
    out = apply_mapping("ods_talent_info_cn", row)
    assert out["profile_type"] == "person"
    assert out["entity_key"]["full_name_employer"] == "李四|上海交通大学"
    assert out["entity_key"]["email"] == "a@b.com"
    assert out["attrs"]["name_cn"] == "李四"
    assert out["attrs"]["highest_degree"] == "博士"
    assert out["attrs"]["gender"] == "男"


def test_unknown_table_returns_none() -> None:
    assert get_mapping("not_a_table") is None
