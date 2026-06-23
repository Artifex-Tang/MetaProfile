"""L2 同义聚类:术语归一(别名词典 + 规范化)→ 稳定 entity_id。
embedding 余弦合并留 P2(共现网)一并做;P1 先用词典归一兜底,保证明显同义合并。"""
from __future__ import annotations
import hashlib
import re

# 别名词典:同义术语归一到规范形。初版手工高频,可扩。
_ALIAS: dict[str, str] = {}
_ALIAS_GROUPS = [
    ("质谱仪", ["质谱仪", "质谱", "mass spectrometry", "mass spectrometer", "MS"]),
    ("液相色谱", ["液相色谱", "high performance liquid chromatography", "HPLC"]),
    ("量子计算", ["量子计算", "quantum computing"]),
]
for canonical, syns in _ALIAS_GROUPS:
    for s in syns:
        _ALIAS[s.lower()] = canonical


def normalize_term(term: str) -> str:
    """术语 → 规范形:别名词典命中返 canonical,否则去标点/空白/小写(中文保留)。"""
    if not term:
        return ""
    t = str(term).strip()
    key = t.lower()
    if key in _ALIAS:
        return _ALIAS[key]
    # 去中英文标点 + 多余空白 + ASCII 小写(中文不受 .lower() 影响,保留)
    t = re.sub(r"[。，,;；:：.。、()\(\)【】\[\]\"'!\?!？]", "", t)
    t = re.sub(r"\s+", "", t)
    return t.lower()


def cluster_entity_id(term: str) -> str:
    """术语 → 稳定 L2 entity_id:concept:{md5(normalized)[:12]}。"""
    n = normalize_term(term)
    if not n:
        return ""
    return "concept:" + hashlib.md5(n.encode("utf-8")).hexdigest()[:12]
