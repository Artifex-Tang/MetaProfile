from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

from metaprofile.shared.worker import translate_tasks


@asynccontextmanager
async def _fake_session_ctx(session_mock):
    yield session_mock


def _patch_session(session_mock):
    """patch get_session() → 每次调用返新 async ctx manager（batch 循环每条独立 session）。"""
    return patch.object(translate_tasks, "get_session",
                        new=lambda: _fake_session_ctx(session_mock))


def test_translate_name_returns_done():
    session = AsyncMock()
    out = MagicMock(); out.translated = True; out.new_value = "量子"
    with _patch_session(session), \
         patch.object(translate_tasks, "translate_name_one", AsyncMock(return_value=out)):
        r = translate_tasks.translate_name("tech", "T1")
    assert r["status"] == "done" and r["translated"] is True


def test_translate_name_failed_returns_failed():
    session = AsyncMock()
    with _patch_session(session), \
         patch.object(translate_tasks, "translate_name_one", AsyncMock(side_effect=Exception("boom"))):
        r = translate_tasks.translate_name("tech", "T1")
    assert r["status"] == "failed" and "boom" in r["error"]


def test_batch_translate_counts():
    session = AsyncMock()
    with _patch_session(session), \
         patch.object(translate_tasks, "_scan_untranslated",
                      AsyncMock(return_value=[("tech", "T1"), ("org", "O1")])), \
         patch.object(translate_tasks, "translate_name_one",
                      AsyncMock(return_value=MagicMock(translated=True, error=None))):
        r = translate_tasks.batch_translate_names(None)
    assert r["status"] == "done" and r["translated"] == 2


def test_batch_translate_skips_and_failed():
    session = AsyncMock()
    results = [MagicMock(translated=False, error=None, reason="no_source"),
               MagicMock(translated=False, error="llm down", reason="")]
    with _patch_session(session), \
         patch.object(translate_tasks, "_scan_untranslated",
                      AsyncMock(return_value=[("tech", "T1"), ("tech", "T2")])), \
         patch.object(translate_tasks, "translate_name_one", AsyncMock(side_effect=results)):
        r = translate_tasks.batch_translate_names("tech")
    assert r["status"] == "done"
    assert r["skipped"] == 1 and r["failed"] == 1 and r["translated"] == 0
