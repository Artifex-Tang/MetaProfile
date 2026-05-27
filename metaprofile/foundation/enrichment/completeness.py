"""
实体完整度评分。

按实体类型定义必填/推荐字段，计算完整度分数，
返回缺失字段列表供 LLM 补全器使用。
"""
from __future__ import annotations

from dataclasses import dataclass, field

from metaprofile.shared.schemas.base import EntityType

# 必填字段（weight=1.0）和推荐字段（weight=0.5）
# 格式：{entity_type: (required_fields, recommended_fields)}
_FIELD_SPEC: dict[EntityType, tuple[list[str], list[str]]] = {
    EntityType.TECH: (
        ["tech_name_cn", "tech_name_en", "tech_domain", "tech_summary", "current_status", "trend"],
        ["dev_goal", "key_points", "autonomy_capability", "tech_advantages", "invention_date"],
    ),
    EntityType.ORG: (
        ["name_cn", "name_en", "country", "founded_date", "summary", "org_types", "function", "tech_domains"],
        ["scale", "website", "strategic_plans", "nature"],
    ),
    EntityType.PERSON: (
        ["name_cn", "name_en", "nationality", "summary", "research_domains"],
        ["birth_date", "title", "edu_background", "current_position"],
    ),
    EntityType.PROJECT: (
        ["project_name", "project_number", "lead_org", "start_date", "summary", "tech_domains"],
        ["end_date", "budget", "project_type", "key_outcomes"],
    ),
}

_REQUIRED_WEIGHT = 1.0
_RECOMMENDED_WEIGHT = 0.5


@dataclass
class CompletenessResult:
    entity_type: EntityType
    score: float                    # 0.0 ~ 1.0
    missing_required: list[str] = field(default_factory=list)
    missing_recommended: list[str] = field(default_factory=list)

    @property
    def needs_enrichment(self) -> bool:
        from metaprofile.shared.config.settings import settings
        return self.score < settings.thresholds.completeness_enrich_trigger

    @property
    def missing_fields(self) -> list[str]:
        return self.missing_required + self.missing_recommended


def score_completeness(
    entity_type: EntityType,
    attributes: dict,
) -> CompletenessResult:
    """
    计算实体完整度。

    分数 = sum(weight of present fields) / sum(weight of all fields)
    """
    required, recommended = _FIELD_SPEC.get(entity_type, ([], []))
    total_weight = len(required) * _REQUIRED_WEIGHT + len(recommended) * _RECOMMENDED_WEIGHT
    if total_weight == 0:
        return CompletenessResult(entity_type=entity_type, score=1.0)

    present_weight = 0.0
    missing_req: list[str] = []
    missing_rec: list[str] = []

    for f in required:
        if _present(attributes.get(f)):
            present_weight += _REQUIRED_WEIGHT
        else:
            missing_req.append(f)

    for f in recommended:
        if _present(attributes.get(f)):
            present_weight += _RECOMMENDED_WEIGHT
        else:
            missing_rec.append(f)

    score = present_weight / total_weight
    return CompletenessResult(
        entity_type=entity_type,
        score=round(score, 4),
        missing_required=missing_req,
        missing_recommended=missing_rec,
    )


def _present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str) and value.strip() == "":
        return False
    if isinstance(value, (list, dict)) and len(value) == 0:
        return False
    return True
