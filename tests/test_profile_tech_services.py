"""
单元测试：profile_tech 五个服务（mock 外部依赖，不需要真实 DB）。
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metaprofile.profile_tech.domain.orm_models import TechProfileORM
from metaprofile.profile_tech.schemas.request import (
    BulkImportRequest,
    SearchRequest,
    SemanticSearchRequest,
    UpdateTechProfileRequest,
)
from metaprofile.profile_tech.schemas.response import (
    TechProfileResponse,
    TechSearchResultList,
)
from metaprofile.profile_tech.services.tech_enrichment_service import TechEnrichmentService
from metaprofile.profile_tech.services.tech_profile_service import TechProfileService
from metaprofile.profile_tech.services.tech_query_service import TechQueryService
from metaprofile.profile_tech.services.tech_relation_service import TechRelationService
from metaprofile.profile_tech.services.tech_stats_service import TechStatsService
from metaprofile.shared.schemas.entity_tech import TechProfile


# ─── helpers ─────────────────────────────────────────────────────────────────

def _make_tech_orm(**kwargs: Any) -> TechProfileORM:
    defaults = dict(
        tech_id="TECH_20260527_abcd1234",
        tech_name_cn="量子计算",
        tech_name_en="Quantum Computing",
        tech_name_other=None,
        tech_domain=["信息技术", "量子物理"],
        invention_date=date(2020, 1, 1),
        application_date=None,
        tech_summary="量子计算利用量子力学原理进行信息处理。",
        dev_goal=None,
        project_layout=[],
        key_points=[],
        transformation_status=None,
        basic_research_status=None,
        autonomy_capability=None,
        industrial_capability=None,
        tech_advantages=None,
        current_status="当前处于实验室阶段。",
        trend="预计2030年实现商业化。",
        remark=None,
        confidence=0.85,
        completeness=0.7,
        veracity_score=0.0,
        timeliness_score=0.0,
        data_as_of=None,
        dev_milestones=[],
        review_impacts=[],
        fundings=[],
        academic_outputs=[],
        experiments=[],
    )
    defaults.update(kwargs)
    orm = MagicMock(spec=TechProfileORM)
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


def _make_minimal_profile(**kwargs: Any) -> TechProfile:
    defaults = dict(
        tech_name_cn="量子计算",
        tech_name_en="Quantum Computing",
        tech_domain=["信息技术"],
        tech_summary="量子计算利用量子力学原理进行信息处理。",
        current_status="处于研究阶段。",
        trend="快速发展中。",
    )
    defaults.update(kwargs)
    return TechProfile(**defaults)


# ─── orm_to_response: 评分字段流通（B1） ──────────────────────────────────────

def test_orm_to_response_exposes_score_fields():
    """veracity_score/timeliness_score/data_as_of 从 ORM 流入 response。"""
    from metaprofile.profile_tech.services.tech_query_service import orm_to_response

    orm = _make_tech_orm(
        veracity_score=0.92,
        timeliness_score=0.81,
        data_as_of=date(2026, 6, 18),
    )
    resp = orm_to_response(orm)
    assert resp.veracity_score == 0.92
    assert resp.timeliness_score == 0.81
    assert resp.data_as_of == date(2026, 6, 18)


# ─── TechQueryService ─────────────────────────────────────────────────────────

class TestTechQueryService:
    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(self):
        svc = TechQueryService()
        session = _make_session_returning(None)
        result = await svc.get_by_id(session, "NO_SUCH_ID")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_returns_response_when_found(self):
        orm = _make_tech_orm()
        session = _make_session_returning(orm)
        svc = TechQueryService()
        result = await svc.get_by_id(session, orm.tech_id)
        assert result is not None
        assert isinstance(result, TechProfileResponse)
        assert result.tech_id == orm.tech_id
        assert result.tech_name_cn == orm.tech_name_cn

    @pytest.mark.asyncio
    async def test_search_empty_payload_returns_list(self):
        session = AsyncMock()
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(side_effect=[count_result, rows_result])

        svc = TechQueryService()
        result = await svc.search(session, SearchRequest())
        assert isinstance(result, TechSearchResultList)
        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_search_with_keyword_constructs_query(self):
        session = AsyncMock()
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        orm = _make_tech_orm()
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = [orm]
        session.execute = AsyncMock(side_effect=[count_result, rows_result])

        svc = TechQueryService()
        result = await svc.search(session, SearchRequest(keyword="量子"))
        assert result.total == 1
        assert result.items[0].tech_id == orm.tech_id

    @pytest.mark.asyncio
    async def test_batch_get_returns_responses(self):
        orm = _make_tech_orm()
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [orm]
        session.execute.return_value = result_mock

        svc = TechQueryService()
        results = await svc.batch_get(session, [orm.tech_id])
        assert len(results) == 1
        assert results[0].tech_id == orm.tech_id

    @pytest.mark.asyncio
    async def test_batch_get_empty_ids_returns_empty(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        session.execute.return_value = result_mock

        svc = TechQueryService()
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

        svc = TechQueryService()
        since = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = await svc.list_changes(session, since=since, until=None, limit=100)
        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_semantic_search_calls_embedding_and_es(self):
        svc = TechQueryService()
        with (
            patch(
                "metaprofile.profile_tech.services.tech_query_service.get_default_embedding_client"
            ) as mock_embed_factory,
            patch.object(svc._es, "knn_search", new_callable=AsyncMock) as mock_knn,
        ):
            mock_embed_client = MagicMock()
            mock_embed_client.embed_one = AsyncMock(return_value=[0.1] * 1024)
            mock_embed_factory.return_value = mock_embed_client
            mock_knn.return_value = []

            result = await svc.semantic_search(
                SemanticSearchRequest(query="量子计算研究进展")
            )
            assert isinstance(result, TechSearchResultList)
            mock_embed_client.embed_one.assert_called_once_with("量子计算研究进展")
            mock_knn.assert_called_once()


# ─── TechProfileService ───────────────────────────────────────────────────────

class TestTechProfileService:
    @pytest.mark.asyncio
    async def test_create_assigns_tech_id_if_missing(self):
        profile = _make_minimal_profile()
        assert profile.tech_id is None

        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        svc = TechProfileService()
        result = await svc.create(session, profile=profile)

        assert result.tech_id is not None
        assert result.tech_id.startswith("TECH_")

    @pytest.mark.asyncio
    async def test_create_adds_orm_and_change_log(self):
        profile = _make_minimal_profile()
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        svc = TechProfileService()
        await svc.create(session, profile=profile)

        # session.add called at least twice: TechProfileORM + EntityChangeLogORM
        assert session.add.call_count >= 2

    @pytest.mark.asyncio
    async def test_create_preserves_existing_tech_id(self):
        profile = _make_minimal_profile(tech_id="TECH_20260527_fixed")
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        svc = TechProfileService()
        result = await svc.create(session, profile=profile)
        assert result.tech_id == "TECH_20260527_fixed"

    @pytest.mark.asyncio
    async def test_update_returns_none_when_not_found(self):
        session = _make_session_returning(None)
        svc = TechProfileService()
        result = await svc.update(
            session,
            tech_id="NO_SUCH",
            payload=UpdateTechProfileRequest(
                tech_name_cn="新名称", operator="test_user"
            ),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_update_writes_change_log_for_changed_fields(self):
        orm = _make_tech_orm(tech_name_cn="旧名称")
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = orm
        session.execute.return_value = result_mock
        session.add = MagicMock()
        session.flush = AsyncMock()

        svc = TechProfileService()
        await svc.update(
            session,
            tech_id=orm.tech_id,
            payload=UpdateTechProfileRequest(
                tech_name_cn="新名称", operator="alice"
            ),
        )
        # At least one EntityChangeLogORM should be added
        assert session.add.call_count >= 1

    @pytest.mark.asyncio
    async def test_bulk_import_returns_task_id(self):
        profiles = [_make_minimal_profile()]
        session = AsyncMock()
        svc = TechProfileService()
        result = await svc.bulk_import(
            session, payload=BulkImportRequest(profiles=profiles)
        )
        assert result.task_id
        assert result.accepted_count == 1


# ─── TechRelationService ──────────────────────────────────────────────────────

class TestTechRelationService:
    @pytest.mark.asyncio
    async def test_list_relations_calls_neo4j_get_neighbors(self):
        svc = TechRelationService()
        with patch.object(
            svc._neo4j, "get_neighbors", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = []
            session = AsyncMock()
            result = await svc.list_relations(
                session, tech_id="TECH_001", relation_type=None, limit=100
            )
            mock_get.assert_called_once_with(
                entity_id="TECH_001", label="Tech", rel_types=None, depth=1
            )
            assert result.total == 0

    @pytest.mark.asyncio
    async def test_list_relations_filters_by_type(self):
        svc = TechRelationService()
        with patch.object(
            svc._neo4j, "get_neighbors", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = [
                {
                    "rel_type": "CONTRIBUTES_TO",
                    "node": {
                        "entity_id": "ORG_001",
                        "entity_type": "ORG",
                        "name": "清华大学",
                        "confidence": 0.9,
                    },
                }
            ]
            session = AsyncMock()
            result = await svc.list_relations(
                session,
                tech_id="TECH_001",
                relation_type="CONTRIBUTES_TO",
                limit=100,
            )
            mock_get.assert_called_once_with(
                entity_id="TECH_001",
                label="Tech",
                rel_types=["CONTRIBUTES_TO"],
                depth=1,
            )
            assert result.total == 1
            assert result.items[0].relation_type == "CONTRIBUTES_TO"

    @pytest.mark.asyncio
    async def test_find_path_returns_not_found_when_empty(self):
        svc = TechRelationService()
        with patch.object(
            svc._neo4j, "find_path", new_callable=AsyncMock
        ) as mock_fp:
            mock_fp.return_value = []
            result = await svc.find_path(
                from_id="TECH_001", to_id="ORG_002", max_depth=4
            )
            assert not result.found
            assert result.paths == []

    @pytest.mark.asyncio
    async def test_find_path_returns_found_when_path_exists(self):
        svc = TechRelationService()
        with patch.object(
            svc._neo4j, "find_path", new_callable=AsyncMock
        ) as mock_fp:
            mock_fp.return_value = [
                [
                    {"entity_id": "TECH_001"},
                    {"entity_id": "ORG_002"},
                ]
            ]
            result = await svc.find_path(
                from_id="TECH_001", to_id="ORG_002", max_depth=4
            )
            assert result.found
            assert len(result.paths) == 1
            assert result.paths[0][0].from_id == "TECH_001"
            assert result.paths[0][0].to_id == "ORG_002"


# ─── TechStatsService ────────────────────────────────────────────────────────

class TestTechStatsService:
    @pytest.mark.asyncio
    async def test_compute_returns_cached_result(self):
        svc = TechStatsService()
        cached_data = dict(
            total=42,
            new_this_period=5,
            updated_this_period=3,
            domain_distribution={"AI": 20},
            completeness_histogram={"60-80": 30},
            llm_contribution_ratio=0.75,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        with patch.object(
            svc._cache, "get", new_callable=AsyncMock, return_value=cached_data
        ):
            session = AsyncMock()
            result = await svc.compute(session)
            assert result.total == 42
            assert result.new_this_period == 5

    @pytest.mark.asyncio
    async def test_compute_caches_on_miss(self):
        svc = TechStatsService()

        def _make_execute_result(scalar_val: Any, all_val: list | None = None):
            m = MagicMock()
            m.scalar_one.return_value = scalar_val
            m.all.return_value = all_val or []
            return m

        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _make_execute_result(10),   # total
                _make_execute_result(2),    # new_count
                _make_execute_result(1),    # updated_count
                _make_execute_result(5),    # total_changes
                _make_execute_result(3),    # llm_count
                _make_execute_result(None, []),  # domain distribution raw
                _make_execute_result(None, []),  # completeness histogram raw
            ]
        )

        with (
            patch.object(svc._cache, "get", new_callable=AsyncMock, return_value=None),
            patch.object(svc._cache, "set", new_callable=AsyncMock) as mock_set,
        ):
            result = await svc.compute(session)
            assert result.total == 10
            mock_set.assert_called_once()


# ─── TechEnrichmentService ────────────────────────────────────────────────────

class TestTechEnrichmentService:
    @pytest.mark.asyncio
    async def test_trigger_returns_none_when_tech_not_found(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.first.return_value = None
        session.execute.return_value = result_mock

        svc = TechEnrichmentService()
        result = await svc.trigger(session, tech_id="NO_SUCH")
        assert result is None

    @pytest.mark.asyncio
    async def test_trigger_dispatches_task_when_below_threshold(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.first.return_value = (0.3,)  # below 0.6 threshold
        session.execute.return_value = result_mock
        fake_result = MagicMock()
        fake_result.id = "celery-task-id"

        with patch(
            "metaprofile.profile_tech.services.tech_enrichment_service.enrich_tech"
        ) as mock_task:
            mock_task.delay.return_value = fake_result
            svc = TechEnrichmentService()
            result = await svc.trigger(session, tech_id="TECH_001")

        assert result is not None
        assert result.status == "queued"
        assert result.task_id == "celery-task-id"
        assert result.current_completeness == pytest.approx(0.3)
        mock_task.delay.assert_called_once_with("TECH_001")

    @pytest.mark.asyncio
    async def test_trigger_returns_skipped_when_above_threshold(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.first.return_value = (0.8,)  # above 0.6 threshold
        session.execute.return_value = result_mock

        svc = TechEnrichmentService()
        result = await svc.trigger(session, tech_id="TECH_001")
        assert result is not None
        assert result.status == "skipped"
        assert result.current_completeness == pytest.approx(0.8)

    @pytest.mark.asyncio
    async def test_get_task_status_success(self):
        with patch(
            "metaprofile.profile_tech.services.tech_enrichment_service.AsyncResult"
        ) as AR:
            inst = MagicMock()
            inst.state = "SUCCESS"
            inst.result = {
                "status": "done",
                "completeness_after": 0.6,
                "filled_fields": ["tech_summary"],
            }
            AR.return_value = inst
            svc = TechEnrichmentService()
            status = await svc.get_task_status("celery-task-id")
        assert status["state"] == "SUCCESS"
        assert status["status"] == "done"
        assert status["completeness_after"] == 0.6
        assert status["filled_fields"] == ["tech_summary"]

    @pytest.mark.asyncio
    async def test_get_task_status_pending(self):
        with patch(
            "metaprofile.profile_tech.services.tech_enrichment_service.AsyncResult"
        ) as AR:
            inst = MagicMock()
            inst.state = "PENDING"
            inst.result = None
            AR.return_value = inst
            svc = TechEnrichmentService()
            status = await svc.get_task_status("celery-task-id")
        assert status["status"] == "pending"
