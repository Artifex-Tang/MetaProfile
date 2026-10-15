"""A 方案:产业技术布局挖掘(企业×IPC 域专利簇)纯函数测试。"""
from __future__ import annotations

from datetime import date

from metaprofile.ingest_ods.services.patent_project_miner import (
    build_profile_rows,
    cluster_patents,
    layout_id,
)


def _rows():
    # 华为 6 件 G06T(成簇);小公司 2 件(不成);中兴 5 件 H04L(成)
    rows = []
    for i in range(6):
        rows.append(("华为技术有限公司", "G06T7/73(2017.01)I", 2020 + i % 5,
                     f"图像处理方法{i}"))
    rows.append(("深圳市小公司", "G06T7/00", 2021, "x"))
    rows.append(("深圳市小公司", "G06T7/00", 2022, "y"))
    for i in range(5):
        rows.append(("中兴通讯股份有限公司", "H04L9/32", 2018 + i % 4, f"安全传输{i}"))
    return rows


def test_cluster_min_patents_threshold():
    clusters = cluster_patents(_rows(), min_patents=5)
    keys = {(c["applicant"], c["ipc"]) for c in clusters}
    assert ("华为技术有限公司", "G06T") in keys
    assert ("中兴通讯股份有限公司", "H04L") in keys
    assert ("深圳市小公司", "G06T") not in keys   # 2 件 < 5
    huawei = next(c for c in clusters if c["applicant"] == "华为技术有限公司")
    assert huawei["patents"] == 6
    assert huawei["years"] == sorted(set(huawei["years"]))


def test_cluster_multi_applicant_split():
    rows = [("甲公司有限公司;乙公司有限公司", "G06N3/08", 2020, "t1"), ("乙公司有限公司", "G06N3/08", 2021, "t2")]
    # 每申请人独立:乙公司 2 件,甲 1 件 → min=2 时乙成簇
    clusters = cluster_patents(rows, min_patents=2)
    assert {c["applicant"] for c in clusters} == {"乙公司有限公司"}


def test_layout_id_stable():
    assert layout_id("华为技术有限公司", "G06T") == layout_id("华为技术有限公司", "G06T")
    assert layout_id("华为技术有限公司", "G06T") != layout_id("华为技术有限公司", "G06N")
    assert layout_id("a", "b").startswith("pp:")


def test_build_profile_rows_fields():
    clusters = cluster_patents(_rows(), min_patents=5)
    rows = build_profile_rows(clusters, {"G06T": "图像数据识别"})
    hw = next(r for r in rows if "华为" in r["name_cn"][0])
    assert hw["name_cn"] == ["华为技术有限公司·图像数据识别技术布局"]
    assert hw["tech_domain"] == ["图像数据识别"]
    assert hw["main_orgs"] == ["华为技术有限公司"]
    assert hw["start_date"] == date(2020, 1, 1)
    assert hw["status"] == "active"          # 年份到 2024 ≥ today-2
    assert hw["project_id"].startswith("pp:")
    # 中文名缺失回落码
    zx = next(r for r in rows if "中兴" in r["name_cn"][0])
    assert "H04L" in zx["name_cn"][0]


def test_weak_signal_sources_default_excludes_market():
    """C 治理:默认源白名单排除 market/key_events。"""
    from metaprofile.shared.config.settings import settings
    srcs = settings.weak_signal.source_list
    assert "market" not in srcs and "key_events" not in srcs
    assert {"science", "patent", "policy"} <= set(srcs)
