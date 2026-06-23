from metaprofile.shared.schemas.relations import RelationType
from metaprofile.profile_tech.domain.orm_models import TechProfileORM
from metaprofile.ingest_ods.domain.orm_models import TechEvidenceORM


def test_relation_type_has_tech_contains():
    assert RelationType.TECH_CONTAINS.value == "包含"


def test_tech_profile_has_layer_columns():
    cols = TechProfileORM.__table__.columns
    assert "tech_layer" in cols
    assert "ipc_code" in cols
    assert "parent_ipc_code" in cols
    assert "cluster_terms" in cols


def test_tech_evidence_orm_fields():
    cols = TechEvidenceORM.__table__.columns
    for c in ("id", "tech_id", "source_doc_id", "source_table", "snippet", "confidence"):
        assert c in cols
