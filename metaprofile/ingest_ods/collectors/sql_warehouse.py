"""source_type='sql_warehouse' 适配器：装配 5 阶段服务 + 跑 orchestrator。

依赖：T3 resolve_dsn / T6 Extractor / T8 EntityResolver / T9 Scorer /
      T10 Writer / T11 ContentMiner / T12 BatchOrchestrator。

Writer/TripleWriter wiring（修复计划 snippet 的 bug）：
计划原稿 `writer = Writer()` 未传 triple_writer，导致 `write_relations` 静默 no-op
（Writer 内部 `self._tw is None` 即返回）。这里在 collector 顶层构造
`tw = TripleWriter(FoundationNeo4jRepo())`（Neo4j repo 同步构造，无 await），
并把它注入 Writer，同一 writer 同时供 orchestrator 与 content-mine 使用，
使关系三元组真正端到端写入 Neo4j。
"""
from __future__ import annotations

import pymysql
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.foundation.relation.triple_writer import TripleWriter
from metaprofile.foundation.storage.neo4j_repo import FoundationNeo4jRepo
from metaprofile.ingest_ods.domain.orm_models import DBConnectionORM
from metaprofile.ingest_ods.services.connections import resolve_dsn
from metaprofile.ingest_ods.services.content_miner import ContentMiner
from metaprofile.ingest_ods.services.extractor import Extractor
from metaprofile.ingest_ods.services.orchestrator import BatchOrchestrator
from metaprofile.ingest_ods.services.resolver import EntityResolver
from metaprofile.ingest_ods.services.scorer import Scorer
from metaprofile.ingest_ods.services.writer import Writer
from metaprofile.shared.llm.gateway import LLMGateway

logger = structlog.get_logger(__name__)


def _fetch_attachments(dsn: dict, table: str, original_ids: list, limit: int = 1000) -> list[dict]:
    """从 SQL 仓库拉取附件 clean_content（SSCursor 流式，避免大结果集 OOM）。"""
    if not original_ids:
        return []
    conn = pymysql.connect(**dsn)
    try:
        cur = conn.cursor(pymysql.cursors.SSCursor)
        ph = ",".join(["%s"] * len(original_ids))
        cur.execute(
            f"SELECT original_id, clean_content FROM `{table}` "
            f"WHERE clean_content IS NOT NULL AND original_id IN ({ph}) LIMIT %s",
            [*original_ids, limit],
        )
        cols = [d[0] for d in cur.description]
        rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        cur.close()
        return rows
    finally:
        conn.close()


async def run_sql_warehouse_collection(
    *,
    task,
    source,
    session: AsyncSession | None = None,
) -> int:
    """装配 5 阶段服务 + 跑 orchestrator；按需触发内容挖掘。

    session 为 None 时自开自管事务（profile 写入）；传入则复用（如 E2E 测试）。
    collector_service._run_collection 不传 session —— 它自己的 session 仅跟踪
    task 状态，两层数据库边界清晰分离。
    """
    from metaprofile.shared.db.postgres import get_session

    llm = LLMGateway()
    # Neo4j repo 单实例:同时喂 TripleWriter(写关系) + Writer(写 profile 节点)，
    # 二者共享同一连接池;profile 节点(entity_id=PK)与关系端点对齐到同一张图。
    neo4j_repo = FoundationNeo4jRepo()
    tw = TripleWriter(neo4j_repo)
    writer = Writer(triple_writer=tw, neo4j_repo=neo4j_repo)

    orch = BatchOrchestrator(
        extractor=Extractor(),
        resolver=EntityResolver(llm=llm),
        scorer=Scorer(llm=llm),
        writer=writer,
        connections=resolve_dsn,
    )

    async def _run(sess):
        imported = await orch.run(sess, task=task, source=source)
        await _maybe_content_mine(sess, source, llm, writer, task=task)
        return imported

    if session is None:
        async with get_session() as sess:
            return await _run(sess)
    return await _run(session)


async def _maybe_content_mine(
    sess: AsyncSession, source, llm, writer: Writer, *, task
) -> None:
    """mode in (content_mine, both) 且 enable_relations → 挖附件 → 写关系三元组。

    I1: 内容挖掘是次要富集；附件拉取/LLM/Neo4j 任一失败都不应杀掉
    orchestrator.run 已写入的结构化灌库结果 —— 整体 try/except 吞掉并记录。

    未映射谓词(unmapped)best-effort 落 relation_staging,失败仅告警不影响主路径。
    """
    cfg = source.config_json or {}
    if cfg.get("mode") not in ("content_mine", "both"):
        return
    if not cfg.get("enable_relations", True):
        return
    try:
        db_id = cfg.get("db_connection_id")  # M6: .get 守卫
        if db_id is None:
            logger.warning("content_mine_skipped_no_db_connection")
            return
        conn_orm = await sess.get(DBConnectionORM, db_id)
        if conn_orm is None:
            logger.warning("content_mine_skipped_no_db_connection_row", db_connection_id=db_id)
            return
        dsn = resolve_dsn(conn_orm)
        att_table = cfg.get("attachment_table", "ods_science_literature_attachment")
        original_ids = cfg.get("content_mine_original_ids") or []  # M3: 处理 None
        original_ids = original_ids[:500]
        if not original_ids:
            logger.info("content_mine_skipped_no_ids")  # M3: 跳过可见化
            return
        atts = _fetch_attachments(dsn, att_table, original_ids)
        if not atts:
            logger.info("content_mine_skipped_no_attachments")
            return
        miner = ContentMiner(llm=llm)
        _entities, relations, unmapped = await miner.mine(atts)
        if relations:
            await writer.write_relations(relations)
            logger.info("content_mine_relations_written", count=len(relations))
        if unmapped:
            try:
                await writer.record_relations_staging(
                    sess, batch_id=task.id, unmapped=unmapped
                )
                logger.info("content_mine_unmapped_staged", count=len(unmapped))
            except Exception as exc:  # noqa: BLE001  staging 失败不杀主路径
                logger.warning("content_mine_staging_failed", error=str(exc))
    except Exception as exc:  # noqa: BLE001  I1: 富集失败不影响结构化灌库结果
        logger.exception("content_mine_failed", error=str(exc))
