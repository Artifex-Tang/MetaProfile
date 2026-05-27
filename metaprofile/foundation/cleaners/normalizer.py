"""
原始文档格式标准化。

职责：
- 字段名映射（各数据源字段名不同 → 统一字段名）
- 日期字符串 → date 对象
- 文本清洗（去控制字符、规范空白）
- 列表字段展平（如 authors 可能是字符串也可能是列表）
"""
from __future__ import annotations

from datetime import date
from typing import Any

import structlog

from metaprofile.foundation.collectors.base import RawDocument
from metaprofile.shared.utils.date_normalizer import normalize_date
from metaprofile.shared.utils.text_normalizer import clean_text, normalize_org_name

logger = structlog.get_logger(__name__)


class NormalizedDoc:
    """标准化后的文档（松散字典，后续由 validator 校验）。"""

    __slots__ = ("source", "doc_type", "raw_id", "url", "lang", "fields")

    def __init__(
        self,
        *,
        source: str,
        doc_type: str,
        raw_id: str,
        url: str | None,
        lang: str,
        fields: dict[str, Any],
    ) -> None:
        self.source = source
        self.doc_type = doc_type
        self.raw_id = raw_id
        self.url = url
        self.lang = lang
        self.fields = fields


# ─── 各数据源字段映射表 ──────────────────────────────────────────────────────
# 格式：{source: {raw_field: normalized_field}}
_FIELD_MAPS: dict[str, dict[str, str]] = {
    "cnipa": {
        "TI": "title",
        "AN": "applicant_name",
        "IN": "inventor_name",
        "IPC": "ipc_codes",
        "AD": "application_date",
        "PD": "publication_date",
        "AB": "abstract",
        "ANE": "application_number",
    },
    "wipo": {
        "title": "title",
        "applicants": "applicant_name",
        "inventors": "inventor_name",
        "ipcCodes": "ipc_codes",
        "applicationDate": "application_date",
        "publicationDate": "publication_date",
        "abstract": "abstract",
        "publicationNumber": "application_number",
    },
    "cnki": {
        "title": "title",
        "author": "authors",
        "organ": "institutions",
        "source": "journal_name",
        "pubdate": "publish_date",
        "summary": "abstract",
        "keyword": "keywords",
        "doi": "doi",
    },
    "wos": {
        "title": "title",
        "authors": "authors",
        "sourceTitle": "journal_name",
        "publishYear": "publish_year",
        "abstract": "abstract",
        "keywords": "keywords",
        "doi": "doi",
        "uid": "wos_id",
    },
    "nsfc": {
        "pjName": "title",
        "pi": "principal_investigator",
        "orgName": "institution",
        "pjNo": "project_number",
        "startYear": "start_year",
        "endYear": "end_year",
        "abstractCn": "abstract",
        "keywords": "keywords",
        "amount": "funding_amount",
    },
    "tianyancha": {
        "name": "org_name",
        "legalPersonName": "legal_person",
        "regStatus": "reg_status",
        "regCapital": "reg_capital",
        "regLocation": "reg_location",
        "estiblishTime": "establish_date",
        "industry": "industry",
        "briefIntroduction": "summary",
    },
    "policy_gov": {
        "title": "title",
        "publishTime": "publish_date",
        "summary": "abstract",
        "url": "source_url",
        "office": "issuing_authority",
    },
    "ccgp": {
        "title": "title",
        "publishTime": "publish_date",
        "purchaseUnit": "buyer",
        "projectCode": "project_code",
        "noticeType": "notice_type",
        "amount": "budget_amount",
    },
}


def normalize(doc: RawDocument) -> NormalizedDoc:
    """将 RawDocument 映射到标准字段。"""
    field_map = _FIELD_MAPS.get(doc.source, {})
    raw = doc.raw_data
    fields: dict[str, Any] = {}

    for raw_key, norm_key in field_map.items():
        val = raw.get(raw_key)
        if val is not None:
            fields[norm_key] = _coerce(norm_key, val)

    # 未映射字段也保留（前缀 raw_）
    for k, v in raw.items():
        if k not in field_map and v is not None:
            fields[f"raw_{k}"] = v

    # 标题来源兜底
    if "title" not in fields and doc.title:
        fields["title"] = clean_text(doc.title)

    return NormalizedDoc(
        source=doc.source,
        doc_type=doc.doc_type,
        raw_id=doc.raw_id,
        url=doc.url,
        lang=doc.lang,
        fields=fields,
    )


def _coerce(field_name: str, value: Any) -> Any:
    """按字段语义进行类型转换。优先级：列表 > 日期 > 机构名 > 通用文本清洗。"""
    if value is None:
        return None

    # 列表字段展平（优先于通用字符串处理）
    if field_name in ("authors", "keywords", "ipc_codes", "institutions"):
        if isinstance(value, str):
            return [s.strip() for s in value.split(";") if s.strip()]
        if isinstance(value, list):
            return [clean_text(str(v)) for v in value if v]

    # 日期字段
    if any(k in field_name for k in ("date", "time", "year")):
        if isinstance(value, (int, str)):
            parsed = normalize_date(str(value))
            return parsed if parsed else value

    # 机构名称标准化
    if "org" in field_name or "institution" in field_name or "applicant" in field_name:
        if isinstance(value, str):
            return normalize_org_name(value)

    # 通用文本清洗
    if isinstance(value, str):
        return clean_text(value)

    return value
