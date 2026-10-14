"""机构名清洗 + 模糊匹配纯函数(Phase D1,零外部依赖)。

rapidfuzz 未进镜像 → stdlib difflib(量级 ≤ 千级名,够用;后续可换 rapidfuzz)。
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

# 常见机构后缀(剥离后比对核心名),中英
_ORG_SUFFIXES = (
    "股份有限公司", "有限责任公司", "有限公司", "集团公司", "集团",
    "大学", "学院", "研究院", "研究所", "研究中心", "实验室",
    "公司", "总部", "分校", "医院",
    "University", "Institute", "Laboratory", "College", "Academy",
    "Corporation", "Company", "Inc", "Ltd", "LLC", "Co", "Corp", "GmbH",
    "of Technology", "of Science", "and Technology", "of Chinese Academy",
)
_FULLWIDTH = str.maketrans("（）［］【】＜＞", "()[][]<>")
_PAREN_RE = re.compile(r"\([^()]*\)|【[^【】]*】|\[[^\[\]]*\]|<[^<>]*>")


def clean_org_name(name: str) -> str:
    """全半角归一 + 去括注(整段删) + 剥后缀(循环至不变)+ 压空白。"""
    if not name:
        return ""
    s = name.strip().translate(_FULLWIDTH)
    s = _PAREN_RE.sub("", s)
    s = re.sub(r"\s+", " ", s).strip()
    changed = True
    while changed:
        changed = False
        low = s.lower()
        for suf in _ORG_SUFFIXES:
            if low.endswith(suf.lower()) and len(s) > len(suf):
                s = s[: -len(suf)].strip(" ,，")
                changed = True
                break
    return s


def similarity(a: str, b: str) -> float:
    """difflib 相似度 [0,1](clean 后比对)。"""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def author_block_key(name: str) -> str:
    """作者 blocking 键:中文(姓=首字 + 名首字) / 英文(surname 末词 + 首字母)。"""
    s = (name or "").strip()
    if not s:
        return ""
    if re.fullmatch(r"[一-鿿·]{2,4}", s):
        return f"{s[0]}|{s[1] if len(s) > 1 else ''}"
    parts = re.split(r"[\s,]+", s.lower())
    if len(parts) >= 2:
        return f"{parts[-1]}|{parts[0][0]}"
    return parts[0][:4]


def coauthor_jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)
