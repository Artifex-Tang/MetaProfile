"""
清洗后字段校验器。

职责：
- 必填字段检查（按 doc_type 不同）
- 字段值范围/格式约束
- 输出 ValidationResult（通过 / 拒绝 / 降级）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import structlog

from metaprofile.foundation.cleaners.normalizer import NormalizedDoc

logger = structlog.get_logger(__name__)


class ValidateOutcome(StrEnum):
    PASS = "pass"       # 全部必填项满足
    DEGRADE = "degrade" # 部分必填缺失，仍可入库但完整度低
    REJECT = "reject"   # 关键字段缺失，不可入库


@dataclass
class ValidationResult:
    outcome: ValidateOutcome
    doc: NormalizedDoc
    missing_required: list[str] = field(default_factory=list)
    missing_recommended: list[str] = field(default_factory=list)
    completeness: float = 1.0   # 0.0~1.0，用于触发 RAG 补全阈值判断


# ─── 各文档类型必填/推荐字段 ────────────────────────────────────────────────
# required：缺失 → REJECT
# recommended：缺失 → DEGRADE，影响 completeness

_RULES: dict[str, dict[str, list[str]]] = {
    "patent": {
        "required": ["title", "application_number"],
        "recommended": ["abstract", "applicant_name", "ipc_codes", "application_date"],
    },
    "paper": {
        "required": ["title"],
        "recommended": ["abstract", "authors", "journal_name", "publish_date", "keywords"],
    },
    "project": {
        "required": ["title", "project_number"],
        "recommended": ["abstract", "principal_investigator", "institution", "start_year"],
    },
    "enterprise": {
        "required": ["org_name"],
        "recommended": ["reg_status", "reg_capital", "establish_date", "industry"],
    },
    "policy": {
        "required": ["title"],
        "recommended": ["abstract", "publish_date", "issuing_authority"],
    },
    "tender": {
        "required": ["title"],
        "recommended": ["publish_date", "buyer", "project_code", "budget_amount"],
    },
}


def validate(doc: NormalizedDoc) -> ValidationResult:
    rules = _RULES.get(doc.doc_type, {"required": [], "recommended": []})
    required_fields: list[str] = rules["required"]
    recommended_fields: list[str] = rules["recommended"]

    missing_req = [f for f in required_fields if not _has_value(doc.fields, f)]
    missing_rec = [f for f in recommended_fields if not _has_value(doc.fields, f)]

    total_fields = len(required_fields) + len(recommended_fields)
    if total_fields == 0:
        completeness = 1.0
    else:
        present = total_fields - len(missing_req) - len(missing_rec)
        completeness = round(present / total_fields, 4)

    if missing_req:
        outcome = ValidateOutcome.REJECT
        logger.warning(
            "doc_validation_reject",
            source=doc.source,
            raw_id=doc.raw_id,
            missing=missing_req,
        )
    elif missing_rec:
        outcome = ValidateOutcome.DEGRADE
    else:
        outcome = ValidateOutcome.PASS

    return ValidationResult(
        outcome=outcome,
        doc=doc,
        missing_required=missing_req,
        missing_recommended=missing_rec,
        completeness=completeness,
    )


def _has_value(fields: dict[str, Any], key: str) -> bool:
    val = fields.get(key)
    if val is None:
        return False
    if isinstance(val, str):
        return bool(val.strip())
    if isinstance(val, (list, dict)):
        return bool(val)
    return True
