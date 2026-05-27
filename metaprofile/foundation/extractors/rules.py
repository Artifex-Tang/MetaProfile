"""
规则抽取器：从结构化字段中用正则/模式提取实体属性。

LLM 抽取前的预处理：能用规则确定的字段不走 LLM。
输入：CleanedDocument.fields
输出：按实体类型归类的规则抽取结果（dict，部分字段已填）
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

import structlog

from metaprofile.shared.schemas.base import EntityType
from metaprofile.shared.utils.date_normalizer import normalize_date

logger = structlog.get_logger(__name__)

# ─── 正则模式 ────────────────────────────────────────────────────────────────

_CN_PATENT_NO = re.compile(r"CN\d{9,12}[A-Z]?(?:\.\d)?", re.IGNORECASE)
_WO_PATENT_NO = re.compile(r"WO\d{4}/\d{6,8}", re.IGNORECASE)
_IPC_CODE     = re.compile(r"[A-H]\d{2}[A-Z]\s*\d+/\d+", re.IGNORECASE)
_NSFC_NO      = re.compile(r"\d{8}")          # 8 位基金编号
_DOI          = re.compile(r"10\.\d{4,9}/\S+")
_EMAIL        = re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}")
_URL          = re.compile(r"https?://\S+")


# ─── 公共入口 ────────────────────────────────────────────────────────────────

def extract_rules(
    doc_type: str,
    fields: dict[str, Any],
) -> dict[str, Any]:
    """
    从 CleanedDocument.fields 中规则抽取可填充的字段。

    返回值与 LLM ExtractionResult 字段名一致，便于后续合并。
    """
    fn = _DISPATCHERS.get(doc_type)
    if fn is None:
        return {}
    try:
        return fn(fields)
    except Exception as exc:
        logger.warning("rules_extract_error", doc_type=doc_type, error=str(exc))
        return {}


# ─── 各类型规则 ──────────────────────────────────────────────────────────────

def _extract_patent(fields: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}

    # 申请号
    app_no = fields.get("application_number", "")
    if app_no:
        result["application_number"] = str(app_no).strip()

    # 从标题/raw 字段二次提取专利号
    title = fields.get("title", "") or ""
    for pat in (fields.get("raw_AN", ""), app_no, title):
        m = _CN_PATENT_NO.search(str(pat))
        if m:
            result["cn_patent_number"] = m.group().upper()
            break
        m = _WO_PATENT_NO.search(str(pat))
        if m:
            result["wo_patent_number"] = m.group().upper()
            break

    # IPC 分类
    ipc_raw = fields.get("ipc_codes") or fields.get("raw_IPC", "")
    if isinstance(ipc_raw, list):
        result["ipc_codes"] = ipc_raw
    elif ipc_raw:
        result["ipc_codes"] = _IPC_CODE.findall(str(ipc_raw))

    # 日期规范化
    for src_field, dst_field in [
        ("application_date", "application_date"),
        ("publication_date", "publication_date"),
    ]:
        raw_date = fields.get(src_field)
        if raw_date:
            parsed = normalize_date(str(raw_date)) if not isinstance(raw_date, date) else raw_date
            if parsed:
                result[dst_field] = parsed

    return result


def _extract_paper(fields: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}

    # DOI
    for key in ("doi", "raw_doi"):
        val = fields.get(key, "")
        if val:
            m = _DOI.search(str(val))
            if m:
                result["doi"] = m.group()
                break

    # 作者列表标准化
    authors = fields.get("authors")
    if isinstance(authors, str):
        result["authors"] = [a.strip() for a in re.split(r"[;，,]", authors) if a.strip()]
    elif isinstance(authors, list):
        result["authors"] = [str(a).strip() for a in authors if a]

    # 关键词标准化
    kws = fields.get("keywords")
    if isinstance(kws, str):
        result["keywords"] = [k.strip() for k in re.split(r"[;，,]", kws) if k.strip()]
    elif isinstance(kws, list):
        result["keywords"] = [str(k).strip() for k in kws if k]

    # 发表日期
    pub_date = fields.get("publish_date")
    if pub_date:
        parsed = normalize_date(str(pub_date)) if not isinstance(pub_date, date) else pub_date
        if parsed:
            result["publish_date"] = parsed

    return result


def _extract_project(fields: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}

    pj_no = fields.get("project_number", "")
    if pj_no:
        result["project_number"] = str(pj_no).strip()
    else:
        # 从标题或其他字段尝试匹配 8 位基金编号
        for key in ("title", "raw_pjNo"):
            m = _NSFC_NO.search(str(fields.get(key, "")))
            if m:
                result["project_number"] = m.group()
                break

    # 年份 → date
    for year_field, date_field in [("start_year", "start_date"), ("end_year", "end_date")]:
        yr = fields.get(year_field)
        if yr:
            parsed = normalize_date(str(yr))
            if parsed:
                result[date_field] = parsed

    return result


def _extract_enterprise(fields: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}

    # 成立日期
    est = fields.get("establish_date")
    if est:
        parsed = normalize_date(str(est)) if not isinstance(est, date) else est
        if parsed:
            result["establish_date"] = parsed

    # 注册资本：提取数字
    cap = str(fields.get("reg_capital", "") or "")
    m = re.search(r"[\d,]+(?:\.\d+)?", cap.replace(",", ""))
    if m:
        try:
            result["reg_capital_amount"] = float(m.group().replace(",", ""))
        except ValueError:
            pass

    return result


def _extract_policy(fields: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    pub = fields.get("publish_date")
    if pub:
        parsed = normalize_date(str(pub)) if not isinstance(pub, date) else pub
        if parsed:
            result["publish_date"] = parsed
    return result


def _extract_tender(fields: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    pub = fields.get("publish_date")
    if pub:
        parsed = normalize_date(str(pub)) if not isinstance(pub, date) else pub
        if parsed:
            result["publish_date"] = parsed

    # 预算金额
    budget = str(fields.get("budget_amount", "") or "")
    m = re.search(r"[\d,]+(?:\.\d+)?", budget.replace(",", ""))
    if m:
        try:
            result["budget_amount"] = float(m.group().replace(",", ""))
        except ValueError:
            pass

    return result


_DISPATCHERS = {
    "patent": _extract_patent,
    "paper": _extract_paper,
    "project": _extract_project,
    "enterprise": _extract_enterprise,
    "policy": _extract_policy,
    "tender": _extract_tender,
}
