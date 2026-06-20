"""
单元测试：profile_project 五个服务（mock 外部依赖，不需要真实 DB）。
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metaprofile.profile_project.domain.orm_models import ProjectProfileORM
from metaprofile.profile_project.schemas.request import (
    BulkImportRequest,
    SearchRequest,
    SemanticSearchRequest,
    UpdateProjectProfileRequest,
)
from metaprofile.profile_project.schemas.response import (
    ProjectProfileResponse,
    ProjectSearchResultList,
)
from metaprofile.profile_project.services.project_enrichment_service import ProjectEnrichmentService
from metaprofile.profile_project.services.project_profile_service import ProjectProfileService
from metaprofile.profile_project.services.project_query_service import ProjectQueryService
from metaprofile.profile_project.services.project_relation_service import ProjectRelationService
from metaprofile.profile_project.services.project_stats_service import ProjectStatsService
from metaprofile.shared.schemas.entity_project import ProjectProfile


# ─── helpers ─────────────────────────────────────────────────────────────────

def _make_project_orm(**kwargs: Any) -> ProjectProfileORM:
    defaults = dict(
        project_id="PROJECT_20260527_abcd1234",
        name_cn=["量子计算研究项目"],
        name_en=["Quantum Computing Research Project"],
        name_other=[],
        tech_domain=["信息技术", "量子物理"],
        sub_tech_domain=[],
        start_date=date(2022, 1, 1),
        cancel_date=None,
        finish_date=None,
        status=["进行中"],
        budget_activities=[],
        project_no=10001,
        main_orgs=["国防部"],
        undertaking_orgs=[],
        undertaking_enterprises=[],
        managers=[],
        researchers=[],
        background=[],
        research_goal="探索量子优势",
        research_content=["量子纠错", "量子通信"],
        keywords=["量子", "计算"],
        progress=["已完成第一阶段"],
        application_prospect=None,
        key_dates=[],
        total_budget_million_usd=50.0,
        invested_million_usd=20.0,
        parent_package_name=None,
        previous_phase_name=None,
        confidence=0.85,
        completeness=0.7,
        veracity_score=0.0,
        timeliness_score=0.0,
        data_as_of=None,
        histories=[],
        budgets=[],
        outputs=[],
    )
    defaults.update(kwargs)
    orm = MagicMock(spec=ProjectProfileORM)
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


def _make_minimal_project(**kwargs: Any) -> ProjectProfile:
    defaults = dict(
        name_cn=["量子计算研究项目"],
        name_en=["Quantum Computing Research Project"],
        tech_domain=["信息技术"],
        start_date=date(2022, 1, 1),
        project_no=10001,
        main_orgs=["国防部"],
        research_content=["量子纠错"],
        progress=["已完成第一阶段"],
    )
    defaults.update(kwargs)
    return ProjectProfile(**defaults)


# ─── orm_to_response: 评分字段流通（B1） ──────────────────────────────────────

def test_orm_to_response_exposes_score_fields():
    """veracity_score/timeliness_score/data_as_of 从 ORM 流入 response。"""
    from metaprofile.profile_project.services.project_query_service import orm_to_response

    orm = _make_project_orm(
        veracity_score=0.83,
        timeliness_score=0.79,
        data_as_of=date(2026, 6, 18),
    )
    resp = orm_to_response(orm)
    assert resp.veracity_score == 0.83
    assert resp.timeliness_score == 0.79
    assert resp.data_as_of == date(2026, 6, 18)


# ─── ProjectQueryService ──────────────────────────────────────────────────────

class TestProjectQueryService:
    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(self):
        svc = ProjectQueryService()
        session = _make_session_returning(None)
        result = await svc.get_by_id(session, "NO_SUCH_ID")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_returns_response_when_found(self):
        orm = _make_project_orm()
        session = _make_session_returning(orm)
        svc = ProjectQueryService()
        result = await svc.get_by_id(session, orm.project_id)
        assert result is not None
        assert isinstance(result, ProjectProfileResponse)
        assert result.project_id == orm.project_id
        assert result.name_cn == orm.name_cn

    @pytest.mark.asyncio
    async def test_search_empty_payload_returns_list(self):
        session = AsyncMock()
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(side_effect=[count_result, rows_result])

        svc = ProjectQueryService()
        result = await svc.search(session, SearchRequest())
        assert isinstance(result, ProjectSearchResultList)
        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_search_with_keyword_constructs_query(self):
        session = AsyncMock()
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        orm = _make_project_orm()
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = [orm]
        session.execute = AsyncMock(side_effect=[count_result, rows_result])

        svc = ProjectQueryService()
        result = await svc.search(session, SearchRequest(keyword="量子"))
        assert result.total == 1
        assert result.items[0].project_id == orm.project_id

    @pytest.mark.asyncio
    async def test_batch_get_returns_responses(self):
        orm = _make_project_orm()
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [orm]
        session.execute.return_value = result_mock

        svc = ProjectQueryService()
        results = await svc.batch_get(session, [orm.project_id])
        assert len(results) == 1
        assert results[0].project_id == orm.project_id

    @pytest.mark.asyncio
    async def test_batch_get_empty_ids_returns_empty(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        session.execute.return_value = result_mock

        svc = ProjectQueryService()
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

        svc = ProjectQueryService()
        since = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = await svc.list_changes(session, since=since, until=None, limit=100)
        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_semantic_search_calls_embedding_and_es(self):
        svc = ProjectQueryService()
        with (
            patch(
                "metaprofile.profile_project.services.project_query_service.get_default_embedding_client"
            ) as mock_embed_factory,
            patch.object(svc._es, "knn_search", new_callable=AsyncMock) as mock_knn,
        ):
            mock_embed_client = MagicMock()
            mock_embed_client.embed_one = AsyncMock(return_value=[0.1] * 1024)
            mock_embed_factory.return_value = mock_embed_client
            mock_knn.return_value = []

            result = await svc.semantic_search(
                SemanticSearchRequest(query="量子计算项目")
            )
            assert isinstance(result, ProjectSearchResultList)
            mock_embed_client.embed_one.assert_called_once_with("量子计算项目")
            mock_knn.assert_called_once()


# ─── ProjectProfileService ────────────────────────────────────────────────────

class TestProjectProfileService:
    @pytest.mark.asyncio
    async def test_create_assigns_project_id_if_missing(self):
        profile = _make_minimal_project()
        assert profile.project_id is None

        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        svc = ProjectProfileService()
        result = await svc.create(session, profile=profile)

        assert result.project_id is not None
        assert result.project_id.startswith("PROJECT_")

    @pytest.mark.asyncio
    async def test_create_adds_orm_and_change_log(self):
        profile = _make_minimal_project()
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        svc = ProjectProfileService()
        await svc.create(session, profile=profile)

        assert session.add.call_count >= 2

    @pytest.mark.asyncio
    async def test_create_preserves_existing_project_id(self):
        profile = _make_minimal_project(project_id="PROJECT_20260527_fixed")
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        svc = ProjectProfileService()
        result = await svc.create(session, profile=profile)
        assert result.project_id == "PROJECT_20260527_fixed"

    @pytest.mark.asyncio
    async def test_update_returns_none_when_not_found(self):
        session = _make_session_returning(None)
        svc = ProjectProfileService()
        result = await svc.update(
            session,
            project_id="NO_SUCH",
            payload=UpdateProjectProfileRequest(
                project_summary="新概述", operator="test_user"
            ),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_update_writes_change_log_for_changed_fields(self):
        orm = _make_project_orm(research_goal="旧概述")
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = orm
        session.execute.return_value = result_mock
        session.add = MagicMock()
        session.flush = AsyncMock()

        svc = ProjectProfileService()
        await svc.update(
            session,
            project_id=orm.project_id,
            payload=UpdateProjectProfileRequest(
                project_summary="新概述", operator="alice"
            ),
        )
        assert session.add.call_count >= 1

    @pytest.mark.asyncio
    async def test_bulk_import_returns_task_id(self):
        profiles = [_make_minimal_project()]
        session = AsyncMock()
        svc = ProjectProfileService()
        result = await svc.bulk_import(
            session, payload=BulkImportRequest(profiles=profiles)
        )
        assert result.task_id
        assert result.accepted_count == 1


# ─── ProjectRelationService ───────────────────────────────────────────────────

class TestProjectRelationService:
    @pytest.mark.asyncio
    async def test_list_relations_calls_neo4j_get_neighbors(self):
        svc = ProjectRelationService()
        with patch.object(
            svc._neo4j, "get_neighbors", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = []
            session = AsyncMock()
            result = await svc.list_relations(
                session, project_id="PROJ_001", relation_type=None, limit=100
            )
            mock_get.assert_called_once_with(
                entity_id="PROJ_001", label="Project", rel_types=None, depth=1
            )
            assert result.total == 0

    @pytest.mark.asyncio
    async def test_list_relations_filters_by_type(self):
        svc = ProjectRelationService()
        with patch.object(
            svc._neo4j, "get_neighbors", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = [
                {
                    "rel_type": "MANAGED_BY",
                    "node": {
                        "entity_id": "ORG_001",
                        "entity_type": "ORG",
                        "name": "国防高研局",
                        "confidence": 0.9,
                    },
                }
            ]
            session = AsyncMock()
            result = await svc.list_relations(
                session,
                project_id="PROJ_001",
                relation_type="MANAGED_BY",
                limit=100,
            )
            mock_get.assert_called_once_with(
                entity_id="PROJ_001",
                label="Project",
                rel_types=["MANAGED_BY"],
                depth=1,
            )
            assert result.total == 1
            assert result.items[0].relation_type == "MANAGED_BY"

    @pytest.mark.asyncio
    async def test_find_path_returns_not_found_when_empty(self):
        svc = ProjectRelationService()
        with patch.object(
            svc._neo4j, "find_path", new_callable=AsyncMock
        ) as mock_fp:
            mock_fp.return_value = []
            result = await svc.find_path(
                from_id="PROJ_001", to_id="ORG_002", max_depth=4
            )
            assert not result.found
            assert result.paths == []

    @pytest.mark.asyncio
    async def test_find_path_returns_found_when_path_exists(self):
        svc = ProjectRelationService()
        with patch.object(
            svc._neo4j, "find_path", new_callable=AsyncMock
        ) as mock_fp:
            mock_fp.return_value = [
                {
                    "nodes": [
                        {"entity_id": "PROJ_001"},
                        {"entity_id": "ORG_002"},
                    ],
                    "rel_types": ["MANAGED_BY"],
                }
            ]
            result = await svc.find_path(
                from_id="PROJ_001", to_id="ORG_002", max_depth=4
            )
            assert result.found
            assert len(result.paths) == 1
            assert result.paths[0][0].from_id == "PROJ_001"
            assert result.paths[0][0].to_id == "ORG_002"


# ─── ProjectStatsService ──────────────────────────────────────────────────────

class TestProjectStatsService:
    @pytest.mark.asyncio
    async def test_compute_returns_cached_result(self):
        svc = ProjectStatsService()
        cached_data = dict(
            total=15,
            new_this_period=3,
            updated_this_period=2,
            domain_distribution={"信息技术": 10},
            completeness_histogram={"60-80": 8},
            llm_contribution_ratio=0.8,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        with patch.object(
            svc._cache, "get", new_callable=AsyncMock, return_value=cached_data
        ):
            session = AsyncMock()
            result = await svc.compute(session)
            assert result.total == 15
            assert result.new_this_period == 3

    @pytest.mark.asyncio
    async def test_compute_caches_on_miss(self):
        svc = ProjectStatsService()

        def _make_execute_result(scalar_val: Any, all_val: list | None = None):
            m = MagicMock()
            m.scalar_one.return_value = scalar_val
            m.all.return_value = all_val or []
            return m

        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _make_execute_result(5),    # total
                _make_execute_result(1),    # new_count
                _make_execute_result(0),    # updated_count
                _make_execute_result(3),    # total_changes
                _make_execute_result(2),    # llm_count
                _make_execute_result(None, []),  # domain distribution raw
                _make_execute_result(None, []),  # completeness histogram raw
            ]
        )

        with (
            patch.object(svc._cache, "get", new_callable=AsyncMock, return_value=None),
            patch.object(svc._cache, "set", new_callable=AsyncMock) as mock_set,
        ):
            result = await svc.compute(session)
            assert result.total == 5
            mock_set.assert_called_once()


# ─── ProjectEnrichmentService ─────────────────────────────────────────────────

class TestProjectEnrichmentService:
    @pytest.mark.asyncio
    async def test_trigger_returns_none_when_project_not_found(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.first.return_value = None
        session.execute.return_value = result_mock

        svc = ProjectEnrichmentService()
        result = await svc.trigger(session, project_id="NO_SUCH")
        assert result is None

    @pytest.mark.asyncio
    async def test_trigger_dispatches_task_when_below_threshold(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.first.return_value = (0.3,)
        session.execute.return_value = result_mock
        fake_result = MagicMock()
        fake_result.id = "celery-task-id"

        with patch(
            "metaprofile.profile_project.services.project_enrichment_service.enrich_project"
        ) as mock_task:
            mock_task.delay.return_value = fake_result
            svc = ProjectEnrichmentService()
            result = await svc.trigger(session, project_id="PROJ_001")

        assert result is not None
        assert result.status == "queued"
        assert result.task_id == "celery-task-id"
        assert result.current_completeness == pytest.approx(0.3)
        mock_task.delay.assert_called_once_with("PROJ_001")

    @pytest.mark.asyncio
    async def test_trigger_returns_skipped_when_above_threshold(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.first.return_value = (0.8,)
        session.execute.return_value = result_mock

        svc = ProjectEnrichmentService()
        result = await svc.trigger(session, project_id="PROJ_001")
        assert result is not None
        assert result.status == "skipped"
        assert result.current_completeness == pytest.approx(0.8)

    @pytest.mark.asyncio
    async def test_get_task_status_success(self):
        with patch(
            "metaprofile.profile_project.services.project_enrichment_service.AsyncResult"
        ) as AR:
            inst = MagicMock()
            inst.state = "SUCCESS"
            inst.result = {"status": "done", "completeness_after": 0.6, "filled_fields": ["summary"]}
            AR.return_value = inst
            svc = ProjectEnrichmentService()
            status = await svc.get_task_status("celery-task-id")
        assert status["state"] == "SUCCESS"
        assert status["status"] == "done"
        assert status["completeness_after"] == 0.6

    @pytest.mark.asyncio
    async def test_get_task_status_pending(self):
        with patch(
            "metaprofile.profile_project.services.project_enrichment_service.AsyncResult"
        ) as AR:
            inst = MagicMock()
            inst.state = "PENDING"
            inst.result = None
            AR.return_value = inst
            svc = ProjectEnrichmentService()
            status = await svc.get_task_status("celery-task-id")
        assert status["status"] == "pending"
