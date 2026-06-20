"""
单元测试：profile_person 五个服务（mock 外部依赖，不需要真实 DB）。
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metaprofile.profile_person.domain.orm_models import PersonProfileORM
from metaprofile.profile_person.schemas.request import (
    BulkImportRequest,
    SearchRequest,
    SemanticSearchRequest,
    UpdatePersonProfileRequest,
)
from metaprofile.profile_person.schemas.response import (
    PersonProfileResponse,
    PersonSearchResultList,
)
from metaprofile.profile_person.services.person_enrichment_service import PersonEnrichmentService
from metaprofile.profile_person.services.person_profile_service import PersonProfileService
from metaprofile.profile_person.services.person_query_service import PersonQueryService
from metaprofile.profile_person.services.person_relation_service import PersonRelationService
from metaprofile.profile_person.services.person_stats_service import PersonStatsService
from metaprofile.shared.schemas.entity_person import PersonProfile


# ─── helpers ─────────────────────────────────────────────────────────────────

def _make_person_orm(**kwargs: Any) -> PersonProfileORM:
    defaults = dict(
        person_id="PERSON_20260527_abcd1234",
        name_cn="张三",
        name_en="Zhang San",
        gender="男",
        avatar=[],
        nationality="中国",
        summary="著名量子物理学家",
        birth_date=date(1975, 6, 15),
        age=50,
        birthplace="北京",
        ethnicity="汉族",
        current_residence="北京",
        current_org="中国科学院",
        current_enterprise=None,
        current_military_unit=None,
        current_position=["研究员"],
        highest_degree="博士",
        person_category="研究",
        professional_domains=["量子物理", "信息技术"],
        professional_skills=["量子算法", "量子纠错"],
        social_media=None,
        personality_traits=[],
        hobbies=[],
        management_philosophy=[],
        remark=[],
        confidence=0.9,
        completeness=0.75,
        veracity_score=0.0,
        timeliness_score=0.0,
        data_as_of=None,
        educations=[],
        careers=[],
        awards=[],
        academic_outputs=[],
        opinions=[],
        reviews=[],
        tech_focuses=[],
        reform_focuses=[],
    )
    defaults.update(kwargs)
    orm = MagicMock(spec=PersonProfileORM)
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


def _make_minimal_person(**kwargs: Any) -> PersonProfile:
    from metaprofile.shared.schemas.entity_person import Gender
    defaults = dict(
        name_cn="张三",
        name_en="Zhang San",
        gender=Gender.MALE,
        nationality="中国",
        summary="著名量子物理学家",
        current_position=["研究员"],
        professional_domains=["量子物理"],
    )
    defaults.update(kwargs)
    return PersonProfile(**defaults)


# ─── orm_to_response: 评分字段流通（B1） ──────────────────────────────────────

def test_orm_to_response_exposes_score_fields():
    """veracity_score/timeliness_score/data_as_of 从 ORM 流入 response。"""
    from metaprofile.profile_person.services.person_query_service import orm_to_response

    orm = _make_person_orm(
        veracity_score=0.91,
        timeliness_score=0.70,
        data_as_of=date(2026, 6, 18),
    )
    resp = orm_to_response(orm)
    assert resp.veracity_score == 0.91
    assert resp.timeliness_score == 0.70
    assert resp.data_as_of == date(2026, 6, 18)


# ─── PersonQueryService ───────────────────────────────────────────────────────

class TestPersonQueryService:
    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_not_found(self):
        svc = PersonQueryService()
        session = _make_session_returning(None)
        result = await svc.get_by_id(session, "NO_SUCH_ID")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_returns_response_when_found(self):
        orm = _make_person_orm()
        session = _make_session_returning(orm)
        svc = PersonQueryService()
        result = await svc.get_by_id(session, orm.person_id)
        assert result is not None
        assert isinstance(result, PersonProfileResponse)
        assert result.person_id == orm.person_id
        assert result.name_cn == orm.name_cn

    @pytest.mark.asyncio
    async def test_search_empty_payload_returns_list(self):
        session = AsyncMock()
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = []
        session.execute = AsyncMock(side_effect=[count_result, rows_result])

        svc = PersonQueryService()
        result = await svc.search(session, SearchRequest())
        assert isinstance(result, PersonSearchResultList)
        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_search_with_keyword_constructs_query(self):
        session = AsyncMock()
        count_result = MagicMock()
        count_result.scalar_one.return_value = 1
        orm = _make_person_orm()
        rows_result = MagicMock()
        rows_result.scalars.return_value.all.return_value = [orm]
        session.execute = AsyncMock(side_effect=[count_result, rows_result])

        svc = PersonQueryService()
        result = await svc.search(session, SearchRequest(keyword="张三"))
        assert result.total == 1
        assert result.items[0].person_id == orm.person_id

    @pytest.mark.asyncio
    async def test_batch_get_returns_responses(self):
        orm = _make_person_orm()
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = [orm]
        session.execute.return_value = result_mock

        svc = PersonQueryService()
        results = await svc.batch_get(session, [orm.person_id])
        assert len(results) == 1
        assert results[0].person_id == orm.person_id

    @pytest.mark.asyncio
    async def test_batch_get_empty_ids_returns_empty(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalars.return_value.all.return_value = []
        session.execute.return_value = result_mock

        svc = PersonQueryService()
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

        svc = PersonQueryService()
        since = datetime(2026, 1, 1, tzinfo=timezone.utc)
        result = await svc.list_changes(session, since=since, until=None, limit=100)
        assert result.total == 0
        assert result.items == []

    @pytest.mark.asyncio
    async def test_semantic_search_calls_embedding_and_es(self):
        svc = PersonQueryService()
        with (
            patch(
                "metaprofile.profile_person.services.person_query_service.get_default_embedding_client"
            ) as mock_embed_factory,
            patch.object(svc._es, "knn_search", new_callable=AsyncMock) as mock_knn,
        ):
            mock_embed_client = MagicMock()
            mock_embed_client.embed_one = AsyncMock(return_value=[0.1] * 1024)
            mock_embed_factory.return_value = mock_embed_client
            mock_knn.return_value = []

            result = await svc.semantic_search(
                SemanticSearchRequest(query="量子物理学家")
            )
            assert isinstance(result, PersonSearchResultList)
            mock_embed_client.embed_one.assert_called_once_with("量子物理学家")
            mock_knn.assert_called_once()


# ─── PersonProfileService ─────────────────────────────────────────────────────

class TestPersonProfileService:
    @pytest.mark.asyncio
    async def test_create_assigns_person_id_if_missing(self):
        profile = _make_minimal_person()
        assert profile.person_id is None

        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        svc = PersonProfileService()
        result = await svc.create(session, profile=profile)

        assert result.person_id is not None
        assert result.person_id.startswith("PERSON_")

    @pytest.mark.asyncio
    async def test_create_adds_orm_and_change_log(self):
        profile = _make_minimal_person()
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        svc = PersonProfileService()
        await svc.create(session, profile=profile)

        assert session.add.call_count >= 2

    @pytest.mark.asyncio
    async def test_create_preserves_existing_person_id(self):
        profile = _make_minimal_person(person_id="PERSON_20260527_fixed")
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()

        svc = PersonProfileService()
        result = await svc.create(session, profile=profile)
        assert result.person_id == "PERSON_20260527_fixed"

    @pytest.mark.asyncio
    async def test_update_returns_none_when_not_found(self):
        session = _make_session_returning(None)
        svc = PersonProfileService()
        result = await svc.update(
            session,
            person_id="NO_SUCH",
            payload=UpdatePersonProfileRequest(
                person_summary="新简介", operator="test_user"
            ),
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_update_writes_change_log_for_changed_fields(self):
        orm = _make_person_orm(summary="旧简介")
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = orm
        session.execute.return_value = result_mock
        session.add = MagicMock()
        session.flush = AsyncMock()

        svc = PersonProfileService()
        await svc.update(
            session,
            person_id=orm.person_id,
            payload=UpdatePersonProfileRequest(
                person_summary="新简介", operator="alice"
            ),
        )
        assert session.add.call_count >= 1

    @pytest.mark.asyncio
    async def test_bulk_import_returns_task_id(self):
        profiles = [_make_minimal_person()]
        session = AsyncMock()
        svc = PersonProfileService()
        result = await svc.bulk_import(
            session, payload=BulkImportRequest(profiles=profiles)
        )
        assert result.task_id
        assert result.accepted_count == 1


# ─── PersonRelationService ────────────────────────────────────────────────────

class TestPersonRelationService:
    @pytest.mark.asyncio
    async def test_list_relations_calls_neo4j_get_neighbors(self):
        svc = PersonRelationService()
        with patch.object(
            svc._neo4j, "get_neighbors", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = []
            session = AsyncMock()
            result = await svc.list_relations(
                session, person_id="PERS_001", relation_type=None, limit=100
            )
            mock_get.assert_called_once_with(
                entity_id="PERS_001", label="Person", rel_types=None, depth=1
            )
            assert result.total == 0

    @pytest.mark.asyncio
    async def test_list_relations_filters_by_type(self):
        svc = PersonRelationService()
        with patch.object(
            svc._neo4j, "get_neighbors", new_callable=AsyncMock
        ) as mock_get:
            mock_get.return_value = [
                {
                    "rel_type": "WORKS_AT",
                    "node": {
                        "entity_id": "ORG_001",
                        "entity_type": "ORG",
                        "name": "中国科学院",
                        "confidence": 0.95,
                    },
                }
            ]
            session = AsyncMock()
            result = await svc.list_relations(
                session,
                person_id="PERS_001",
                relation_type="WORKS_AT",
                limit=100,
            )
            mock_get.assert_called_once_with(
                entity_id="PERS_001",
                label="Person",
                rel_types=["WORKS_AT"],
                depth=1,
            )
            assert result.total == 1
            assert result.items[0].relation_type == "WORKS_AT"

    @pytest.mark.asyncio
    async def test_find_path_returns_not_found_when_empty(self):
        svc = PersonRelationService()
        with patch.object(
            svc._neo4j, "find_path", new_callable=AsyncMock
        ) as mock_fp:
            mock_fp.return_value = []
            result = await svc.find_path(
                from_id="PERS_001", to_id="ORG_002", max_depth=4
            )
            assert not result.found
            assert result.paths == []

    @pytest.mark.asyncio
    async def test_find_path_returns_found_when_path_exists(self):
        svc = PersonRelationService()
        with patch.object(
            svc._neo4j, "find_path", new_callable=AsyncMock
        ) as mock_fp:
            mock_fp.return_value = [
                {
                    "nodes": [
                        {"entity_id": "PERS_001"},
                        {"entity_id": "ORG_002"},
                    ],
                    "rel_types": ["WORKS_AT"],
                }
            ]
            result = await svc.find_path(
                from_id="PERS_001", to_id="ORG_002", max_depth=4
            )
            assert result.found
            assert len(result.paths) == 1
            assert result.paths[0][0].from_id == "PERS_001"
            assert result.paths[0][0].to_id == "ORG_002"


# ─── PersonStatsService ───────────────────────────────────────────────────────

class TestPersonStatsService:
    @pytest.mark.asyncio
    async def test_compute_returns_cached_result(self):
        svc = PersonStatsService()
        cached_data = dict(
            total=100,
            new_this_period=8,
            updated_this_period=5,
            domain_distribution={"量子物理": 30},
            completeness_histogram={"60-80": 50},
            llm_contribution_ratio=0.7,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
        with patch.object(
            svc._cache, "get", new_callable=AsyncMock, return_value=cached_data
        ):
            session = AsyncMock()
            result = await svc.compute(session)
            assert result.total == 100
            assert result.new_this_period == 8

    @pytest.mark.asyncio
    async def test_compute_caches_on_miss(self):
        svc = PersonStatsService()

        def _make_execute_result(scalar_val: Any, all_val: list | None = None):
            m = MagicMock()
            m.scalar_one.return_value = scalar_val
            m.all.return_value = all_val or []
            return m

        session = AsyncMock()
        session.execute = AsyncMock(
            side_effect=[
                _make_execute_result(20),   # total
                _make_execute_result(4),    # new_count
                _make_execute_result(2),    # updated_count
                _make_execute_result(10),   # total_changes
                _make_execute_result(7),    # llm_count
                _make_execute_result(None, []),  # domain distribution raw
                _make_execute_result(None, []),  # completeness histogram raw
            ]
        )

        with (
            patch.object(svc._cache, "get", new_callable=AsyncMock, return_value=None),
            patch.object(svc._cache, "set", new_callable=AsyncMock) as mock_set,
        ):
            result = await svc.compute(session)
            assert result.total == 20
            mock_set.assert_called_once()


# ─── PersonEnrichmentService ──────────────────────────────────────────────────

class TestPersonEnrichmentService:
    @pytest.mark.asyncio
    async def test_trigger_returns_none_when_person_not_found(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.first.return_value = None
        session.execute.return_value = result_mock

        svc = PersonEnrichmentService()
        result = await svc.trigger(session, person_id="NO_SUCH")
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
            "metaprofile.profile_person.services.person_enrichment_service.enrich_person"
        ) as mock_task:
            mock_task.delay.return_value = fake_result
            svc = PersonEnrichmentService()
            result = await svc.trigger(session, person_id="PERS_001")

        assert result is not None
        assert result.status == "queued"
        assert result.task_id == "celery-task-id"
        assert result.current_completeness == pytest.approx(0.3)
        mock_task.delay.assert_called_once_with("PERS_001")

    @pytest.mark.asyncio
    async def test_trigger_returns_skipped_when_above_threshold(self):
        session = AsyncMock()
        result_mock = MagicMock()
        result_mock.first.return_value = (0.8,)
        session.execute.return_value = result_mock

        svc = PersonEnrichmentService()
        result = await svc.trigger(session, person_id="PERS_001")
        assert result is not None
        assert result.status == "skipped"
        assert result.current_completeness == pytest.approx(0.8)

    @pytest.mark.asyncio
    async def test_get_task_status_success(self):
        with patch(
            "metaprofile.profile_person.services.person_enrichment_service.AsyncResult"
        ) as AR:
            inst = MagicMock()
            inst.state = "SUCCESS"
            inst.result = {"status": "done", "completeness_after": 0.6, "filled_fields": ["summary"]}
            AR.return_value = inst
            svc = PersonEnrichmentService()
            status = await svc.get_task_status("celery-task-id")
        assert status["state"] == "SUCCESS"
        assert status["status"] == "done"
        assert status["completeness_after"] == 0.6

    @pytest.mark.asyncio
    async def test_get_task_status_pending(self):
        with patch(
            "metaprofile.profile_person.services.person_enrichment_service.AsyncResult"
        ) as AR:
            inst = MagicMock()
            inst.state = "PENDING"
            inst.result = None
            AR.return_value = inst
            svc = PersonEnrichmentService()
            status = await svc.get_task_status("celery-task-id")
        assert status["status"] == "pending"
