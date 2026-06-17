"""BatchOrchestrator：批次 + 并发(Semaphore) + 同 profile_type 互斥 + 断点续传。"""
from __future__ import annotations

import asyncio
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.ingest_ods.domain.orm_models import DBConnectionORM
from metaprofile.ingest_ods.services.connections import resolve_dsn
from metaprofile.ingest_ods.services.watermark import WatermarkStore

logger = structlog.get_logger(__name__)

# 进程内活跃 profile_type 集合 → 同类型互斥，跨类型并行
_active_types: set[str] = set()


class BatchOrchestrator:
    def __init__(self, *, extractor, resolver, scorer, writer,
                 connections=resolve_dsn) -> None:
        self._extractor = extractor
        self._resolver = resolver
        self._scorer = scorer
        self._writer = writer
        self._connections = connections

    async def run(self, session: AsyncSession, *, task, source) -> int:
        cfg = source.config_json or {}
        tables: list[str] = cfg.get("table_set", [])
        workers: int = int(cfg.get("workers", 4))
        batch_size: int = int(cfg.get("batch_size", workers * 125))
        mode: str = cfg.get("mode", "structured_only")
        watermark: str | None = WatermarkStore.get(source, WatermarkStore.KEY_WM)

        conn_orm = await session.get(DBConnectionORM, cfg["db_connection_id"])
        dsn = self._connections(conn_orm)

        total_imported = 0
        for table in tables:
            last_id = WatermarkStore.get(source, WatermarkStore.KEY_ID) or 0
            while True:
                rows = await self._extractor.extract_batch(
                    dsn=dsn, table=table, last_id=last_id,
                    batch_size=batch_size, watermark=watermark,
                )
                if not rows:
                    break
                last_id = rows[-1]["last_id"]
                # 同 profile_type 互斥（这里按表产出类型；简化：取首行类型）
                ptype = rows[0]["profile_type"]
                while ptype in _active_types:
                    await asyncio.sleep(0.5)
                _active_types.add(ptype)
                try:
                    imported = await self._process_batch(session, task, source, rows, mode)
                    total_imported += imported
                finally:
                    _active_types.discard(ptype)

                WatermarkStore.set(source, WatermarkStore.KEY_ID, last_id)
                await session.flush()
        return total_imported

    async def _process_batch(self, session, task, source, rows, mode) -> int:
        # TODO: 并发执行 entity 评分/写入（asyncio.Semaphore(workers)），当前批量较小时顺序执行即可。
        # mode == "content_mine" / "both" 的附件内容挖掘由 ContentMiner 在 collector (T13) 层接入，
        # 这里仅负责结构化抽取路径。
        # resolve 整批（消歧需跨行）
        entities = await self._resolver.resolve(rows)
        imported = 0
        for ent in entities:
            # EntityResolver 通常归一为 {profile_type, entity_key, attrs, source_rows}；
            # 兼容“直通”/未归一化的原始抽取行（attrs 缺失时回退 raw_payload._attrs）。
            attrs = ent.get("attrs")
            if attrs is None:
                attrs = (ent.get("raw_payload") or {}).get("_attrs", {}) or {}
            scores = await self._scorer.score(
                profile_type=ent["profile_type"], attrs=attrs,
                source_rows=ent.get("source_rows", []),
            )
            entity_id = (ent["entity_key"].get("company_id")
                         or ent["entity_key"].get("usc_code")
                         or ent["entity_key"].get("orcid")
                         or ent["entity_key"].get("email")
                         or ent["entity_key"].get("patent_number")
                         or ent["entity_key"].get("doi")
                         or f"name:{attrs.get('name_cn') or attrs.get('tech_name_cn')}")
            try:
                await self._writer.write_profile(
                    session, profile_type=ent["profile_type"], entity_id=str(entity_id),
                    attrs=attrs, scores=scores, method="llm_extract",
                )
                imported += 1
            except Exception as exc:  # noqa: BLE001
                await self._writer.record_error(
                    session, batch_id=task.id, stage="write",
                    error_msg=str(exc), source_table=rows[0].get("source_table"),
                )
        await session.commit()
        task.records_imported = (task.records_imported or 0) + imported
        return imported
