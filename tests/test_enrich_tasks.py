"""单元测试：shared/worker/enrich_tasks —— celery 任务包裹 typed ORM 补全核心。"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from metaprofile.shared.enrich.orm_enricher import EnrichOutcome
from metaprofile.shared.schemas.base import EntityType


def test_shape_done():
    from metaprofile.shared.worker.enrich_tasks import _shape
    out = EnrichOutcome(
        entity_id="T1", entity_type=EntityType.TECH,
        completeness_before=0.35, completeness_after=0.59,
        filled_fields=["tech_summary"],
    )
    d = _shape(out, "T1")
    assert d["status"] == "done"
    assert d["entity_id"] == "T1"
    assert d["completeness_before"] == 0.35
    assert d["completeness_after"] == 0.59
    assert d["filled_fields"] == ["tech_summary"]
    assert d["error"] is None


def test_shape_skipped():
    from metaprofile.shared.worker.enrich_tasks import _shape
    out = EnrichOutcome(
        entity_id="T1", entity_type=EntityType.TECH,
        completeness_before=0.9, completeness_after=0.9, skipped=True,
    )
    assert _shape(out, "T1")["status"] == "skipped"


def test_shape_error():
    from metaprofile.shared.worker.enrich_tasks import _shape
    out = EnrichOutcome(
        entity_id="T1", entity_type=EntityType.TECH,
        completeness_before=0.0, completeness_after=0.0, error="entity_not_found",
    )
    assert _shape(out, "T1")["status"] == "error"
    assert _shape(out, "T1")["error"] == "entity_not_found"


def test_enrich_tech_task_calls_core_and_shapes():
    from metaprofile.shared.worker import enrich_tasks

    fake_outcome = EnrichOutcome(
        entity_id="TECH_1", entity_type=EntityType.TECH,
        completeness_before=0.3, completeness_after=0.6,
        filled_fields=["tech_summary"],
    )

    fake_session = MagicMock()
    cm = AsyncMock()
    cm.__aenter__.return_value = fake_session
    cm.__aexit__.return_value = None

    with patch.object(enrich_tasks, "get_session", return_value=cm), \
         patch.object(enrich_tasks, "enrich_one", new=AsyncMock(return_value=fake_outcome)) as mock_core:
        result = enrich_tasks.enrich_tech("TECH_1")

    assert result["status"] == "done"
    assert result["completeness_after"] == 0.6
    mock_core.assert_awaited_once()
    # 传给核心的 entity_type / orm_cls 正确
    _, kwargs = mock_core.call_args
    assert kwargs["entity_type"] == EntityType.TECH
    assert kwargs["change_log_entity_type"] == "tech"
    assert kwargs["entity_id"] == "TECH_1"
