from __future__ import annotations

from metaprofile.ingest_ods.domain.orm_models import (
    DBConnectionORM, IngestRawORM, RelationStagingORM, IngestErrorORM,
)
from metaprofile.profile_tech.domain.orm_models import TechProfileORM
from metaprofile.profile_org.domain.orm_models import OrgProfileORM
from metaprofile.profile_person.domain.orm_models import PersonProfileORM
from metaprofile.profile_project.domain.orm_models import ProjectProfileORM


def _cols(orm_cls) -> set[str]:
    return {c.name for c in orm_cls.__table__.columns}


def test_db_connections_columns() -> None:
    c = _cols(DBConnectionORM)
    assert {"name", "dialect", "host", "port", "database", "username",
            "password_enc", "pool_size", "read_only", "is_enabled"} <= c


def test_staging_columns() -> None:
    assert {"profile_type", "source_table", "source_id", "entity_key",
            "raw_payload", "batch_id", "status"} <= _cols(IngestRawORM)
    assert {"batch_id", "subject_name", "subject_type", "object_name",
            "object_type", "relation", "confidence", "written"} <= _cols(RelationStagingORM)
    assert {"batch_id", "source_table", "source_id", "stage",
            "error_msg"} <= _cols(IngestErrorORM)


def test_profile_score_columns_added() -> None:
    for orm_cls in (TechProfileORM, OrgProfileORM, PersonProfileORM, ProjectProfileORM):
        assert {"veracity_score", "timeliness_score", "data_as_of"} <= _cols(orm_cls)
