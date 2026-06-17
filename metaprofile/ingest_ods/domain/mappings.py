"""表→画像 字段映射注册表。扩展新表：往 MAPPINGS 加条目即可。"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class FieldMap:
    src: Any                          # 源列名(str)或可调用(_feat(...) 产出)
    target: str                       # 目标画像字段
    transform: Callable[[Any], Any] | None = None


@dataclass
class MappingSet:
    profile_type: str
    key_fields: list[str]             # 用作 entity_key 的源列
    fields: list[FieldMap] = field(default_factory=list)


def _feat(name: str) -> Callable[[Any], Any]:
    """从 row['features'][name] 取值（features 是 dict 或 JSON 字符串）。"""
    def f(row: dict) -> Any:
        feat = row.get("features")
        if isinstance(feat, str):
            try:
                feat = json.loads(feat)
            except Exception:
                feat = {}
        if not isinstance(feat, dict):
            return None
        return feat.get(name)
    return f


def _one(value: Any) -> list:
    return [value] if value not in (None, "") else []


MAPPINGS: dict[str, MappingSet] = {
    "ods_company_basic_info": MappingSet(
        profile_type="org",
        key_fields=["company_id", "usc_code"],
        fields=[
            FieldMap("company_id", "org_id"),
            FieldMap("company_name", "name_cn"),
            FieldMap("company_enname", "name_en"),
            FieldMap("usc_code", "usc_code"),
            FieldMap("category_name", "tech_domains", _one),
            FieldMap("province", "country"),
            FieldMap("estiblish_time", "founded_date"),
            FieldMap("business_scope", "summary"),
            FieldMap("legal_person_name", "legal_person"),
            FieldMap("reg_capital", "reg_capital"),
            FieldMap("pension_count", "scale_raw"),
        ],
    ),
    "ods_talent_info_cn": MappingSet(
        profile_type="person",
        key_fields=["full_name", "employer"],   # 复合键见下方 _build_key
        fields=[
            FieldMap("full_name", "name_cn"),
            FieldMap("education", "highest_degree"),
            FieldMap("job_title", "current_position", _one),
            FieldMap("employer", "current_org"),
            FieldMap(_feat("sex"), "gender"),
            FieldMap(_feat("mail"), "email"),
            FieldMap(_feat("discipline"), "professional_domains", _one),
            FieldMap(_feat("graduatedUniversity"), "graduated_university"),
        ],
    ),
    "ods_science_literature": MappingSet(
        profile_type="tech",
        key_fields=["title"],
        fields=[
            FieldMap("title", "tech_name_cn"),
            FieldMap("abstract", "tech_summary"),
            FieldMap("keyword", "key_points"),
            FieldMap(_feat("doi"), "doi"),
            FieldMap(_feat("pubdate"), "invention_date"),
        ],
    ),
    "ods_invention_patent_cn": MappingSet(
        profile_type="tech",
        key_fields=["title"],
        fields=[
            FieldMap("title", "tech_name_cn"),
            FieldMap("ipc_type", "tech_domain", _one),
            FieldMap("legal_status", "current_status"),
            FieldMap("filing_date", "application_date"),
            FieldMap("applicant", "applicant"),
            FieldMap(_feat("Patent_number"), "patent_number"),
            FieldMap(_feat("Inventor"), "inventors"),
        ],
    ),
    "ods_market_analysis_cn": MappingSet(
        profile_type="project",
        key_fields=["title", "purchaser", "region"],
        fields=[
            FieldMap("title", "name_cn", _one),
            FieldMap("purchaser", "main_orgs", _one),
            FieldMap("region", "region"),
            FieldMap("announcement_type", "status", _one),
            FieldMap("amount", "total_budget_raw"),
            FieldMap("event_time", "start_date"),
            FieldMap(_feat("budget_amount"), "budget_raw"),
            FieldMap(_feat("project_contact"), "managers", _one),
        ],
    ),
}


def get_mapping(table: str) -> MappingSet | None:
    return MAPPINGS.get(table)


def _resolve(row: dict, src: Any) -> Any:
    """src 可以是字符串列名，也可以是 _feat(...) 产出的可调用。"""
    if callable(src):
        return src(row)
    return row.get(src)


def _build_key(table: str, row: dict, mset: MappingSet) -> dict:
    key: dict[str, Any] = {}
    if table == "ods_talent_info_cn":
        name = row.get("full_name")
        emp = row.get("employer")
        if name and emp:
            key["full_name_employer"] = f"{name}|{emp}"
    else:
        for k in mset.key_fields:
            v = row.get(k)
            if v not in (None, ""):
                key[k] = v
    # email/orcid/doi/patent_number 等从 features 补
    for feat_name, key_name in (("mail", "email"), ("orcid_pub", "orcid"),
                                ("doi", "doi"), ("Patent_number", "patent_number")):
        v = _feat(feat_name)(row)
        if v:
            key[key_name] = v
    return key


def apply_mapping(table: str, row: dict) -> dict | None:
    """row(dict) → {profile_type, entity_key, attrs}；表未注册返回 None。"""
    mset = MAPPINGS.get(table)
    if mset is None:
        return None
    attrs: dict[str, Any] = {}
    for fm in mset.fields:
        val = _resolve(row, fm.src)
        if fm.transform and val is not None:
            val = fm.transform(val)
        if val not in (None, "", []):
            attrs[fm.target] = val
    return {
        "profile_type": mset.profile_type,
        "entity_key": _build_key(table, row, mset),
        "attrs": attrs,
    }
