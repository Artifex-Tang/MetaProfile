"""
单元测试：foundation/storage 层（mock 外部连接，不需要真实 DB）。

测试重点：
- PostgresRepo 方法逻辑正确（使用 AsyncMock session）
- UnifiedRepo 的 outbox fallback 行为
- FoundationNeo4jRepo 的 write_relation 参数映射
"""
from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metaprofile.foundation.storage.es_repo import FoundationESRepo
from metaprofile.foundation.storage.neo4j_repo import FoundationNeo4jRepo
from metaprofile.foundation.storage.postgres_repo import PostgresRepo
from metaprofile.foundation.storage.unified_repo import UnifiedRepo
from metaprofile.shared.schemas.base import EntityType, SourceMethod
from metaprofile.shared.schemas.relations import RelationTriple, RelationType


# ─── PostgresRepo ────────────────────────────────────────────────────────────

@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.add = MagicMock()
    session.delete = AsyncMock()
    return session


@pytest.fixture
def pg_repo(mock_session):
    return PostgresRepo(session=mock_session)


@pytest.mark.asyncio
async def test_postgres_repo_upsert_calls_execute(pg_repo, mock_session):
    await pg_repo.upsert(
        EntityType.TECH,
        "TECH_001",
        {"tech_name_cn": "量子计算"},
    )
    mock_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_postgres_repo_find_by_id_returns_none_when_empty(pg_repo, mock_session):
    # mock scalars to return None
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    mock_session.execute.return_value = result_mock

    result = await pg_repo.find_by_id(EntityType.TECH, "TECH_001")
    assert result is None


@pytest.mark.asyncio
async def test_postgres_repo_find_by_id_returns_data(pg_repo, mock_session):
    row_mock = MagicMock()
    row_mock.data = {"tech_name_cn": "量子计算"}
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = row_mock
    mock_session.execute.return_value = result_mock

    result = await pg_repo.find_by_id(EntityType.TECH, "TECH_001")
    assert result == {"tech_name_cn": "量子计算"}


@pytest.mark.asyncio
async def test_postgres_repo_outbox_enqueue_adds_record(pg_repo, mock_session):
    await pg_repo.outbox_enqueue(
        target="es",
        entity_id="TECH_001",
        payload={"data": "value"},
    )
    mock_session.add.assert_called_once()
    added = mock_session.add.call_args[0][0]
    assert added.target == "es"
    assert added.entity_id == "TECH_001"
    assert added.status == "pending"


# ─── UnifiedRepo fallback ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unified_repo_es_failure_falls_back_to_outbox():
    pg = AsyncMock(spec=PostgresRepo)
    es = AsyncMock(spec=FoundationESRepo)
    neo = AsyncMock(spec=FoundationNeo4jRepo)

    # ES upsert 失败
    es.upsert_entity.side_effect = ConnectionError("ES unreachable")

    repo = UnifiedRepo(postgres_repo=pg, es_repo=es, neo4j_repo=neo)
    await repo.upsert_entity(
        entity_type=EntityType.TECH,
        entity_id="TECH_001",
        attributes={"tech_name_cn": "量子计算"},
    )

    pg.upsert.assert_called_once()
    pg.outbox_enqueue.assert_called_once()
    call_kwargs = pg.outbox_enqueue.call_args.kwargs
    assert call_kwargs["target"] == "es"
    assert call_kwargs["entity_id"] == "TECH_001"


@pytest.mark.asyncio
async def test_unified_repo_neo4j_failure_falls_back_to_outbox():
    pg = AsyncMock(spec=PostgresRepo)
    es = AsyncMock(spec=FoundationESRepo)
    neo = AsyncMock(spec=FoundationNeo4jRepo)

    neo.upsert_entity_node.side_effect = ConnectionError("Neo4j unreachable")

    repo = UnifiedRepo(postgres_repo=pg, es_repo=es, neo4j_repo=neo)
    await repo.upsert_entity(
        entity_type=EntityType.ORG,
        entity_id="ORG_001",
        attributes={"org_name_cn": "中国科学院"},
    )

    pg.outbox_enqueue.assert_called_once()
    call_kwargs = pg.outbox_enqueue.call_args.kwargs
    assert call_kwargs["target"] == "neo4j"


@pytest.mark.asyncio
async def test_unified_repo_postgres_failure_propagates():
    pg = AsyncMock(spec=PostgresRepo)
    pg.upsert.side_effect = RuntimeError("DB down")
    es = AsyncMock(spec=FoundationESRepo)
    neo = AsyncMock(spec=FoundationNeo4jRepo)

    repo = UnifiedRepo(postgres_repo=pg, es_repo=es, neo4j_repo=neo)
    with pytest.raises(RuntimeError, match="DB down"):
        await repo.upsert_entity(
            entity_type=EntityType.TECH,
            entity_id="TECH_001",
            attributes={},
        )

    # ES/Neo4j 不应被调用
    es.upsert_entity.assert_not_called()
    neo.upsert_entity_node.assert_not_called()


# ─── FoundationNeo4jRepo ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_neo4j_repo_write_relation():
    mock_inner = AsyncMock()
    repo = FoundationNeo4jRepo(repo=mock_inner)

    triple = RelationTriple(
        subject_id="TECH_001",
        subject_type=EntityType.TECH,
        subject_name="量子计算",
        relation=RelationType.TECH_CONTRIBUTOR,
        object_id="ORG_001",
        object_type=EntityType.ORG,
        object_name="中科院",
        confidence=0.9,
        method=SourceMethod.RULE,
        extracted_at=datetime.now(UTC),
    )
    await repo.write_relation(triple)

    mock_inner.upsert_relation.assert_called_once()
    kwargs = mock_inner.upsert_relation.call_args.kwargs
    assert kwargs["from_label"] == "Tech"
    assert kwargs["to_label"] == "Org"
    assert kwargs["rel_type"] == RelationType.TECH_CONTRIBUTOR.value


def test_neo4j_repo_label_mapping():
    repo = FoundationNeo4jRepo(repo=MagicMock())
    assert repo.label(EntityType.TECH) == "Tech"
    assert repo.label(EntityType.ORG) == "Org"
    assert repo.label(EntityType.PERSON) == "Person"
    assert repo.label(EntityType.PROJECT) == "Project"
