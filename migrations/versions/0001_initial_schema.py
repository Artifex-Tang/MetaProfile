"""初始 Schema：创建全部表结构。

Revision ID: 0001
Revises:
Create Date: 2026-05-27

此迁移使用 Base.metadata.create_all / drop_all，
等效于手动 DDL 但无需逐表书写 op.create_table。
适合第一次部署到空数据库。
后续字段变更改用标准 op.add_column / op.drop_column 增量迁移。
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 导入所有 ORM 模型确保 Base.metadata 完整
    _import_all_models()
    from metaprofile.shared.db.base import Base
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    _import_all_models()
    from metaprofile.shared.db.base import Base
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)


def _import_all_models() -> None:
    import metaprofile.foundation.storage.orm_models  # noqa: F401
    import metaprofile.shared.db.orm_models  # noqa: F401
    import metaprofile.profile_tech.domain.orm_models  # noqa: F401
    import metaprofile.profile_org.domain.orm_models  # noqa: F401
    import metaprofile.profile_project.domain.orm_models  # noqa: F401
    import metaprofile.profile_person.domain.orm_models  # noqa: F401
    import metaprofile.scan_monitor.domain.orm_models  # noqa: F401
    import metaprofile.new_tech_discovery.domain.orm_models  # noqa: F401
    import metaprofile.topic_selection.domain.orm_models  # noqa: F401
    import metaprofile.settings_api.domain.orm_models  # noqa: F401
    import metaprofile.ingest_ods.domain.orm_models  # noqa: F401
