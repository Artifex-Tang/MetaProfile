#!/usr/bin/env python3
"""
代码骨架生成脚本：把 profile_tech 完整样板镜像到 profile_project / profile_org / profile_person。

执行：python scripts/gen_profile_skeletons.py
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "metaprofile"
SOURCE = "profile_tech"

# (target_pkg, snake, type_pascal, type_chinese, schema_module, profile_class, extraction_class)
TARGETS = [
    ("profile_project", "project", "Project", "项目", "entity_project", "ProjectProfile", "ProjectExtractionResult"),
    ("profile_org",     "org",     "Org",     "机构", "entity_org",     "OrgProfile",     "OrgExtractionResult"),
    ("profile_person",  "person",  "Person",  "人员", "entity_person",  "PersonProfile",  "PersonExtractionResult"),
]

# 把 profile_tech 中的 tech / Tech / TECH / 技术 替换为目标
def transform(text: str, snake: str, pascal: str, chinese: str) -> str:
    # 顺序很重要：先长后短，先大写后小写
    text = text.replace("profile_tech", f"profile_{snake}")
    text = text.replace("TechProfile", f"{pascal}Profile")
    text = text.replace("TechExtractionResult", f"{pascal}ExtractionResult")
    text = text.replace("TechSearchResultItem", f"{pascal}SearchResultItem")
    text = text.replace("TechSearchResultList", f"{pascal}SearchResultList")
    text = text.replace("TechProfileResponse", f"{pascal}ProfileResponse")
    text = text.replace("TechProfileORM", f"{pascal}ProfileORM")
    text = text.replace("TechDevMilestoneORM", f"{pascal}DevMilestoneORM")
    text = text.replace("TechReviewImpactORM", f"{pascal}ReviewImpactORM")
    text = text.replace("TechFundingORM", f"{pascal}FundingORM")
    text = text.replace("TechAcademicOutputORM", f"{pascal}AcademicOutputORM")
    text = text.replace("TechExperimentORM", f"{pascal}ExperimentORM")
    text = text.replace("TechStatsResponse", f"{pascal}StatsResponse")
    text = text.replace("TechExtractor", f"{pascal}Extractor")
    text = text.replace("TechProfileService", f"{pascal}ProfileService")
    text = text.replace("TechQueryService", f"{pascal}QueryService")
    text = text.replace("TechRelationService", f"{pascal}RelationService")
    text = text.replace("TechStatsService", f"{pascal}StatsService")
    text = text.replace("TechEnrichmentService", f"{pascal}EnrichmentService")
    text = text.replace("Tech", pascal)  # 兜底
    text = text.replace("/profile/tech", f"/profile/{snake}")
    text = text.replace("/relation/tech", f"/relation/{snake}")
    text = text.replace("/stats/tech", f"/stats/{snake}")
    text = text.replace("tech_id", f"{snake}_id")
    text = text.replace("tech_name_cn", f"{snake}_name_cn")
    text = text.replace("tech_name_en", f"{snake}_name_en")
    text = text.replace("tech_domain", f"{snake}_domain")
    text = text.replace("tech_summary", f"{snake}_summary")
    text = text.replace("tech_advantages", f"{snake}_advantages")
    text = text.replace("tech_extractor", f"{snake}_extractor")
    text = text.replace("tech_profile", f"{snake}_profile")
    text = text.replace("\"tech\"", f"\"{snake}\"")
    text = text.replace("'tech'", f"'{snake}'")
    text = text.replace("EntityType.TECH", f"EntityType.{pascal.upper() if pascal != 'Project' else 'PROJECT'}")
    text = text.replace("from metaprofile.shared.schemas.entity_tech import",
                        f"from metaprofile.shared.schemas.entity_{snake} import" if snake != "person" else "from metaprofile.shared.schemas.entity_person import")
    text = text.replace("技术画像", f"{chinese}画像")
    text = text.replace("技术实体", f"{chinese}实体")
    text = text.replace("技术", chinese)
    return text


def main():
    src_dir = ROOT / SOURCE
    for target_pkg, snake, pascal, chinese, schema_module, profile_class, extraction_class in TARGETS:
        tgt_dir = ROOT / target_pkg
        for src_path in src_dir.rglob("*.py"):
            rel = src_path.relative_to(src_dir)
            new_name = str(rel).replace("tech_", f"{snake}_")
            tgt_path = tgt_dir / new_name
            tgt_path.parent.mkdir(parents=True, exist_ok=True)
            content = src_path.read_text(encoding="utf-8")
            transformed = transform(content, snake, pascal, chinese)
            tgt_path.write_text(transformed, encoding="utf-8")
            print(f"  {tgt_path.relative_to(ROOT.parent)}")


if __name__ == "__main__":
    main()
