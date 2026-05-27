"""日期标准化为 yyyy-MM-dd（数据规范要求）。"""
from __future__ import annotations

import re
from datetime import date, datetime

DATE_PATTERNS = [
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y年%m月%d日",
    "%Y.%m.%d",
    "%Y%m%d",
    "%Y-%m",
    "%Y/%m",
    "%Y年%m月",
    "%Y",
]


def normalize_date(raw: str | None) -> date | None:
    """将各种格式日期统一为 date。仅有年份时返回 yyyy-01-01。"""
    if not raw:
        return None
    raw = raw.strip()
    # 抓取连续数字与分隔符
    cleaned = re.sub(r"\s+", "", raw)

    for pat in DATE_PATTERNS:
        try:
            return datetime.strptime(cleaned, pat).date()
        except ValueError:
            continue
    return None


def to_iso_date(d: date | None) -> str | None:
    return d.isoformat() if d else None
