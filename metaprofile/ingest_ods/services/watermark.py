"""last_id / last_watermark 存取（落在 DataSourceConfigORM.config_json）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any


class WatermarkStore:
    KEY_ID = "last_id"
    KEY_WM = "last_watermark"

    @staticmethod
    def get(source, key: str) -> Any:
        return (source.config_json or {}).get(key)

    @staticmethod
    def set(source, key: str, value: Any) -> None:
        cfg = dict(source.config_json or {})
        cfg[key] = value.isoformat() if isinstance(value, datetime) else value
        source.config_json = cfg  # 触发 ORM 脏标记
