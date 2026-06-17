from datetime import datetime, timezone
from unittest.mock import MagicMock

from metaprofile.ingest_ods.services.watermark import WatermarkStore


def _source() -> MagicMock:
    s = MagicMock()
    s.config_json = {}
    return s


def test_get_returns_none_when_unset() -> None:
    assert WatermarkStore.get(_source(), "last_id") is None


def test_set_and_get_roundtrip() -> None:
    src = _source()
    WatermarkStore.set(src, "last_id", 12345)
    assert src.config_json["last_id"] == 12345
    assert WatermarkStore.get(src, "last_id") == 12345


def test_set_watermark_datetime() -> None:
    src = _source()
    ts = datetime(2026, 6, 17, tzinfo=timezone.utc)
    WatermarkStore.set(src, "last_watermark", ts)
    assert WatermarkStore.get(src, "last_watermark") == ts.isoformat()
