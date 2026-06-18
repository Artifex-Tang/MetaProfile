"""
单元测试：profile_org 五个服务（mock 外部依赖，不需要真实 DB）。
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metaprofile.profile_org.domain.orm_models import OrgProfileORM
from metaprofile.profile_org.schemas.request import (
    BulkImportRequest,
    SearchRequest,
    SemanticSearchRequest,
    UpdateOrgProfileRequest,
)
from metaprofile.profile_org.schemas.response import (
    OrgProfileResponse,
    OrgSearchResultList,
)
from metaprofile.profile_org.services.org_enrichment_service import OrgEnrichmentService
from metaprofile.profile_org.services.org_profile_service import OrgProfileService
from metaprofile.profile_org.services.org_query_service import OrgQueryService
from metaprofile.profile_org.services.org_relation_service import OrgRelationService
from metaprofile.profile_org.services.org_stats_service import OrgStatsService
from metaprofile.shared.schemas.entity_org import OrgNature, OrgProfile, OrgType


# ─── helpers ─────────────────────────────────────────────────────────────────

def _make_org_orm(**kwargs: Any) -> OrgProfileORM:
    defaults = dict(
        org_id="ORG_20260527_abcd1234",
        name_cn="国防高研局",
        name_en="DARPA",
        name_other=[],
        country="美国",
        founded_date=date(1958, 2, 7),
        dissolved_date=None,
        operating_years=68,
        website="https://darpa.mil",
        summary="美国国防高级研究计划局",
        org_types=["管理机构"],
        nature="实体机构",
        function="资助前沿科技研究",
        scale=220,
        tech_domains=["信息技术", "人工智能"],
        predecessor_names=[],
        departments=None,
        strategic_plans=[],
        evaluation_report=None,
        new_key_projects=[],
        remark=None,
        confidence=0.95,
        completeness=0.8,
        veracity_score=0.0,
        timeliness_score=0.0,
        data_as_of=None,
        histories=[],
        affiliations=[],
        awards=[],
        budgets=[],
        fundings_received=[],
        outputs=[],
        reviews=[],
        addresses=[],
        activities=[],
        team=None,
        facilities=[],
    )
    defaults.update(kwargs)
    orm = MagicMock(spec=OrgProfileORM)
    for k, v in defaults.items():
        setattr(orm, k, v)
    return orm


def _make_session_returning(value: Any) -> AsyncMock:
    session = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    result.scalar_one.return_value = value if isinstance(value, int) else 0
    result.scalars.return_value.all.return_value = [value] if value else []
    result.first.return_value = (value,) if value is not None else None
    session.execute.return_value = result
    session.add = MagicMock()
    session.flush = AsyncMock()
    return session


def _make_minimal_org(**kwargs: Any) -> OrgProfile:
    defaults = dict(
        name_cn="国防高研局",
        name_en="DARPA",
        country="美国",
        founded_date=date(1958, 2, 7),
        operating_years=68,
        summary="美国国防高级研究计划局",
        org_types=[OrgType.GOVT],
        nature=OrgNature.ENTITY,
        function="资助前沿科技研究",
        tech_domains=["信息技术"],
    )
    defaults.update(kwargs)
    return OrgProfile(**defaults)


# ─── orm_to_response: 评分字段流通（B1） ──────────────────────────────────────

def test_orm_to_response_exposes_score_fields():
    """veracity_score/timeliness_score/data_as_of 从 ORM 流入 response。"""
    from metaprofile.profile_org.services.org_query_service import orm_to_response

    orm = _make_org_orm(
        veracity_score=0.88,
        timeliness_score=0.76,
        data_as_of=date(2026, 6, 18),
    )
    resp = orm_to_response(orm)
    assert resp.veracity_score == 0.88
    assert resp.timeliness_score == 0.76
    assert resp.data_as_of == date(2026, 6, 18)


# ─── OrgQueryService ──────────────────────────────────────────────────────────

class TestOrgQueryService:
    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(self):
        svc = OrgQueryService()
        session = _make_session_returning(None)
        result = await svc.get_by_id(session, "NO_SUCH_ID")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_returns_response_when_found(self):
        orm = _make_org_orm()
        session = _make_session_returning(orm)
        svc = OrgQueryService()
        result = await svc.get_by_id(session, orm.org_id)
        assert result is not None
        assert isinstance(result, OrgProfileResponse)
        assert result.org_id == orm.org_id
        assert result.name_cn == orm.name_cn

    @pytest.mark.asyncio
    async def test_search_empty_payload_returns_list(self):
        session = AsyncMock()
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(side_effect=[count_result, rows_result])

        svc = OrgQueryService()
        result = await svc.search(session, SearchRequest())
        assert isinstance(result, OrgSearchResultList)
        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_search_with_keyword_constructs_query(self):
        session = AsyncMock()
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        orm = _make_org_orm()
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = [orm]
        session.execute = AsyncMock(side_effect=[count_result, rows_result])

        svc = OrgQueryService()
        result = await svc.search(session, SearchRequest(keyword="DARPA"))
        assert result.total == 1
        assert result.items[0].org_id == orm.org_id

    @pytest.mark.asyncio
    async def test_batch_get_returns_responses(self):
        orm = _make_org_orm()
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [orm]
        session.execute.return_value = result_mock

        svc = OrgQueryService()
        results = await svc.batch_get(session, [orm.org_id])
        assert len(results) == 1
        assert results[0].org_id == orm.org_id

    @pytest.mark.asyncio
    async def test_batch_get_empty_ids_returns_empty(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        session.execute.return_value = result_mock

        svc = OrgQueryService()
        results = await svc.batch_get(session, [])
        assert results == []

    @pytest.mark.asyncio
    async def test_list_changes_returns_empty_list(self):
        session = AsyncMock()
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(side_effect=[count_result, rows_result])

        svc = OrgQueryService()
        since = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = await svc.list_changes(session, since=since, until=None, limit=100)
        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_semantic_search_calls_embedding_and_es(self):
        svc = OrgQueryService()
        with (
            patch(
                "metaprofile.profile_org.services.org_query_service.get_default_embedding_client"
            ) as mock_embed_factory,
            patch.object(svc._es, "knn_search", new_callable=AsyncMock) as mock_knn,
        ):
            mock_embed_client = MagicMock()
            mock_embed_client.embed_one = AsyncMock(return_value=[0.1] * 1024)
            mock_embed_factory.return_value = mock_embed_client
            mock_knn.return_value = []

            result = await svc.semantic_search(
                SemanticSearchRequest(query="前沿科技研究机构")
            )
            assert isinstance(result, OrgSearchResultList)
            mock_embed_client.embed_one.assert_called_once_with("前沿科技研究机构")
            mock_knn.assert_called_once()


# ─── OrgProfileService ────────────────────────────────────────────────────────

class TestOrgProfileService:
    @pytest.mark.asyncio
    async def test_create_assigns_org_id_if_missing(self):
        profile = _make_minimal_org()
        assert profile.org_id is None

        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        svc = OrgProfileService()
        result = await svc.create(session, profile=profile)

        assert result.org_id is not None
        assert result.org_id.startswith("ORG_")

    @pytest.mark.asyncio
    async def test_create_adds_orm_and_change_log(self):
        profile = _make_minimal_org()
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        svc = OrgProfileService()
        await svc.create(session, profile=profile)

        assert session.add.call_count >= 2

    @pytest.mark.asyncio
    async def test_create_preserves_existing_org_id(self):
        profile = _make_minimal_org(org_id="ORG_20260527_fixed")
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        svc = OrgProfileService()
        result = await svc.create(session, profile=profile)
        assert result.org_id == "ORG_20260527_fixed"

    @pytest.mark.asyncio
    async def test_update_returns_none_when_not_found(self):
        session = _make_session_returning(None)
        svc = OrgProfileService()
        result = await svc.update(
            session,
            org_id="NO_SUCH",
            payload=UpdateOrgProfileRequest(
                org_summary="新简介", operator="test_user"
            ),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_update_writes_change_log_for_changed_fields(self):
        orm = _make_org_orm(summary="旧简介")
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = orm
        session.execute.return_value = result_mock
        session.add = MagicMock()
        session.flush = AsyncMock()

        svc = OrgProfileService()
        await svc.update(
            session,
            org_id=orm.org_id,
            payload=UpdateOrgProfileRequest(
                org_summary="新简介", operator="alice"
            ),
        )
        assert session.add.call_count >= 1

    @pytest.mark.asyncio
    async def test_bulk_import_returns_task_id(self):
        profiles = [_make_minimal_org()]
        session = AsyncMock()
        svc = OrgProfileService()
        result = await svc.bulk_import(
            session, payload=BulkImportRequest(profiles=profiles)
        )
        assert result.task_id
        assert result.accepted_count == 1


# ─── OrgRelationService ───────────────────────────────────────────────────────

class TestOrgRelationService:
    @pytest.mark.asyncio
    async def test_list_relations_calls_neo4j_get_neighbors(self):
        svc = OrgRelationService()
        with patch.object(
            svc._neo4j, "get_neighbors", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = []
            session = AsyncMock()
            result = await svc.list_relations(
                session, org_id="ORG_001", relation_type=None, limit=100
            )
            mock_get.assert_called_once_with(
                entity_id="ORG_001", label="Org", rel_types=None, depth=1
            )
            assert result.total == 0

    @pytest.mark.asyncio
    async def test_list_relations_filters_by_type(self):
        svc = OrgRelationService()
        with patch.object(
            svc._neo4j, "get_neighbors", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = [
                {
                    "rel_type": "MANAGES",
                    "node": {
                        "entity_id": "PROJ_001",
                        "entity_type": "PROJECT",
                        "name": "量子计算项目",
                        "confidence": 0.88,
                    },
                }
            ]
            session = AsyncMock()
            result = await svc.list_relations(
                session,
                org_id="ORG_001",
                relation_type="MANAGES",
                limit=100,
            )
            mock_get.assert_called_once_with(
                entity_id="ORG_001",
                label="Org",
                rel_types=["MANAGES"],
                depth=1,
            )
            assert result.total == 1
            assert result.items[0].relation_type == "MANAGES"

    @pytest.mark.asyncio
    async def test_find_path_returns_not_found_when_empty(self):
        svc = OrgRelationService()
        with patch.object(
            svc._neo4j, "find_path", new_callable=AsyncMock
        ) as mock_fp:
            mock_fp.return_value = []
            result = await svc.find_path(
                from_id="ORG_001", to_id="PROJ_002", max_depth=4
            )
            assert not result.found
            assert result.paths == []

    @pytest.mark.asyncio
    async def test_find_path_returns_found_when_path_exists(self):
        svc = OrgRelationService()
        with patch.object(
            svc._neo4j, "find_path", new_callable=AsyncMock
        ) as mock_fp:
            mock_fp.return_value = [
                [
                    {"entity_id": "ORG_001"},
                    {"entity_id": "PROJ_002"},
                ]
            ]
            result = await svc.find_path(
                from_id="ORG_001", to_id="PROJ_002", max_depth=4
            )
            assert result.found
            assert len(result.paths) == 1
            assert result.paths[0][0].from_id == "ORG_001"
            assert result.paths[0][0].to_id == "PROJ_002"


# ─── OrgStatsService ──────────────────────────────────────────────────────────

class TestOrgStatsService:
    @pytest.mark.asyncio
    async def test_compute_returns_cached_result(self):
        svc = OrgStatsService()
        cached_data = dict(
            total=50,
            new_this_period=6,
            updated_this_period=4,
            domain_distribution={"信息技术": 25},
            completeness_histogram={"60-80": 30},
            llm_contribution_ratio=0.65,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        with patch.object(
            svc._cache, "get", new_callable=AsyncMock, return_value=cached_data
        ):
            session = AsyncMock()
            result = await svc.compute(session)
            assert result.total == 50
            assert result.new_this_period == 6

    @pytest.mark.asyncio
    async def test_compute_caches_on_miss(self):
        svc = OrgStatsService()

        def _make_execute_result(scalar_val: Any, all_val: list | None = None):
            m = MagicMock()
            m.scalar_one.return_value = scalar_val
            m.all.return_value = all_val or []
            return m

        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _make_execute_result(8),    # total
                _make_execute_result(2),    # new_count
                _make_execute_result(1),    # updated_count
                _make_execute_result(6),    # total_changes
                _make_execute_result(4),    # llm_count
                _make_execute_result(None, []),  # domain distribution raw
                _make_execute_result(None, []),  # completeness histogram raw
            ]
        )

        with (
            patch.object(svc._cache, "get", new_callable=AsyncMock, return_value=None),
            patch.object(svc._cache, "set", new_callable=AsyncMock) as mock_set,
        ):
            result = await svc.compute(session)
            assert result.total == 8
            mock_set.assert_called_once()


# ─── OrgEnrichmentService ─────────────────────────────────────────────────────

class TestOrgEnrichmentService:
    @pytest.mark.asyncio
    async def test_trigger_returns_none_when_org_not_found(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.first.return_value = None
        session.execute.return_value = result_mock

        svc = OrgEnrichmentService()
        result = await svc.trigger(session, org_id="NO_SUCH")
        assert result is None

    @pytest.mark.asyncio
    async def test_trigger_returns_queued_when_below_threshold(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.first.return_value = (0.3,)
        session.execute.return_value = result_mock

        svc = OrgEnrichmentService()
        result = await svc.trigger(session, org_id="ORG_001")
        assert result is not None
        assert result.status == "queued"
        assert result.current_completeness == pytest.approx(0.3)

    @pytest.mark.asyncio
    async def test_trigger_returns_skipped_when_above_threshold(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.first.return_value = (0.8,)
        session.execute.return_value = result_mock

        svc = OrgEnrichmentService()
        result = await svc.trigger(session, org_id="ORG_001")
        assert result is not None
        assert result.status == "skipped"
        assert result.current_completeness == pytest.approx(0.8)

    @pytest.mark.asyncio
    async def test_trigger_returns_task_id(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.first.return_value = (0.4,)
        session.execute.return_value = result_mock

        svc = OrgEnrichmentService()
        result = await svc.trigger(session, org_id="ORG_001")
        assert result is not None
        assert len(result.task_id) == 32
        assert result.org_id == "ORG_001"
