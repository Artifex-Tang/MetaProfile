from datetime import date, timedelta

from metaprofile.ingest_ods.services.quality_rules import (
    authority_bonus,
    consistency_factor,
    credibility_score,
    timeliness_score,
)


def test_timeliness_fresh():
    assert timeliness_score(date.today()) == 1.0


def test_timeliness_halflife():
    s = timeliness_score(date.today() - timedelta(days=180))
    assert 0.49 <= s <= 0.51


def test_timeliness_none():
    assert timeliness_score(None) == 0.0


def test_timeliness_old():
    assert timeliness_score(date.today() - timedelta(days=3650)) < 0.01


def test_authority_bonus_cap():
    attrs = {"doi": "10.1/x", "citation": "ref", "patent_no": "P1", "usc_code": "U1"}
    assert authority_bonus(attrs) == 0.15


def test_authority_bonus_none():
    assert authority_bonus({}) == 0.0


def test_consistency_ok():
    assert (
        consistency_factor("tech", {"invention_date": date(2020, 1, 1), "application_date": date(2021, 1, 1)})
        == 1.0
    )


def test_consistency_bad_dates():
    assert (
        consistency_factor("tech", {"invention_date": date(2022, 1, 1), "application_date": date(2021, 1, 1)})
        == 0.85
    )


def test_consistency_missing_dates():
    assert consistency_factor("tech", {}) == 1.0


def test_credibility_ods_with_doi():
    src = {"source_table": "ods_science_literature"}
    attrs = {"doi": "10.1/x"}
    assert abs(credibility_score(src, attrs) - 0.95) < 0.001


def test_credibility_cap_and_factor():
    src = {"source_table": "ods_x"}
    attrs = {
        "doi": "1",
        "citation": "2",
        "patent_no": "3",
        "invention_date": date(2022, 1, 1),
        "application_date": date(2021, 1, 1),
    }
    assert abs(credibility_score(src, attrs) - 0.8925) < 0.001


def test_consistency_project_ok():
    from datetime import date
    assert consistency_factor("project", {"start_date": date(2021,1,1), "end_date": date(2022,1,1)}) == 1.0

def test_consistency_project_bad():
    from datetime import date
    assert consistency_factor("project", {"start_date": date(2022,1,1), "end_date": date(2021,1,1)}) == 0.85

def test_consistency_org_person_noop():
    # org/person 无日期一致性检查 → 恒 ok(v1 局限)
    assert consistency_factor("org", {}) == 1.0
    assert consistency_factor("person", {}) == 1.0
