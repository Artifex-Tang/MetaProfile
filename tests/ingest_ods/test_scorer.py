import asyncio
from datetime import date, timedelta
from metaprofile.ingest_ods.services.scorer import RuleScorer


def test_score_returns_all_five_fields():
    s = RuleScorer()
    attrs = {"tech_name_cn": "量子计算", "tech_name_en": "q", "tech_domain": ["量子"],
             "tech_summary": "x", "current_status": "emerging", "trend": "up",
             "doi": "10.1/x"}
    src = [{"source_table": "ods_science_literature",
            "raw_payload": {"update_time": str(date.today() - timedelta(days=10))}}]
    out = asyncio.run(s.score("tech", attrs, src))
    for k in ("completeness", "veracity_score", "timeliness_score", "data_as_of", "dq_index"):
        assert k in out, f"missing {k}"
    assert 0 < out["completeness"] <= 1.0
    assert out["veracity_score"] > 0.8        # ods 0.9 + doi 0.05 = 0.95
    assert out["timeliness_score"] > 0.9      # 10 天前 ≈0.96
    assert 0 < out["dq_index"] <= 1.0


def test_score_no_data_as_of_timeliness_zero():
    s = RuleScorer()
    out = asyncio.run(s.score("tech", {"tech_name_cn": "x"},
                              [{"source_table": "ods_y", "raw_payload": {}}]))
    assert out["timeliness_score"] == 0.0
    assert out["data_as_of"] is None


def test_dq_index_perfect_when_all_fields_and_authority():
    # 全 req+rec 字段 → completeness=1.0；3 权威信号 → veracity=clamp(0.9+0.15)=1.0；今日 → timeliness=1.0
    # → dq_index = 0.4*1 + 0.3*1 + 0.3*1 = 1.0
    s = RuleScorer()
    attrs = {f: "v" for f in [
        "tech_name_cn", "tech_name_en", "tech_domain", "tech_summary", "current_status", "trend",
        "dev_goal", "key_points", "autonomy_capability", "tech_advantages", "invention_date",
        "doi", "citation", "patent_no",
    ]}
    src = [{"source_table": "ods_x", "raw_payload": {"update_time": str(date.today())}}]
    out = asyncio.run(s.score("tech", attrs, src))
    assert abs(out["dq_index"] - 1.0) < 0.01, out
    assert abs(out["completeness"] - 1.0) < 0.01


def test_score_org_person_project_keys_in_range():
    s = RuleScorer()
    cases = [
        ("org", {"name_cn": "机构", "name_en": "org", "country": "CN", "summary": "x"}),
        ("person", {"name_cn": "张三", "name_en": "zs", "nationality": "CN", "summary": "x"}),
        ("project", {"project_name": "项目", "project_number": "P1", "lead_org": "o", "summary": "x"}),
    ]
    src = [{"source_table": "ods_x", "raw_payload": {"update_time": str(date.today())}}]
    for ptype, attrs in cases:
        out = asyncio.run(s.score(ptype, attrs, src))
        for k in ("completeness", "veracity_score", "timeliness_score", "data_as_of", "dq_index"):
            assert k in out, f"{ptype} missing {k}"
        assert 0.0 <= out["dq_index"] <= 1.0
        assert 0.0 <= out["veracity_score"] <= 1.0

def test_score_future_update_time_not_treated_fresh():
    # 未来日期不应让 timeliness=1.0(I4: _latest_as_of 跳过未来)
    s = RuleScorer()
    future = str(date.today() + timedelta(days=365))
    out = asyncio.run(s.score("tech", {"tech_name_cn": "x"},
                              [{"source_table": "ods_y", "raw_payload": {"update_time": future}}]))
    assert out["timeliness_score"] != 1.0
    # 全未来 → data_as_of None → timeliness 0
    assert out["data_as_of"] is None
    assert out["timeliness_score"] == 0.0
