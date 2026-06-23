"""BatchOrchestrator：批次 + 并发(Semaphore) + 同 profile_type 互斥 + 断点续传。"""
from __future__ import annotations

import asyncio
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from metaprofile.ingest_ods.domain.mappings import get_mapping
from metaprofile.ingest_ods.domain.orm_models import DBConnectionORM
from metaprofile.ingest_ods.domain.relation_rules import (
    NAME_SATELLITE_PREFIX,
    extract_structured_relations,
)
from metaprofile.ingest_ods.services.connections import resolve_dsn
from metaprofile.ingest_ods.services.name_index import NameIndex
from metaprofile.ingest_ods.services.watermark import WatermarkStore
from metaprofile.shared.schemas.base import EntityType
from metaprofile.shared.schemas.relations import RelationTriple

logger = structlog.get_logger(__name__)

# 强键优先级（依次尝试，返回首个存在值的 str(...)）
_STRONG_KEYS: tuple[str, ...] = (
    "company_id", "usc_code", "orcid", "patent_number", "doi", "email",
)

# profile_type(lowercase str) → EntityType
_PT2ET: dict[str, EntityType] = {
    "tech": EntityType.TECH,
    "org": EntityType.ORG,
    "person": EntityType.PERSON,
    "project": EntityType.PROJECT,
}

# tech_concept 阶段处理的源表(专利 / 论文):title+abstract 是 LLM 抽术语的语料。
_TECH_TABLES: tuple[str, ...] = ("ods_invention_patent_cn", "ods_science_literature")

# 证据 snippet 截断长度 —— 对齐 TechEvidenceORM.snippet 列预算。
_EVIDENCE_SNIPPET_MAX = 500


def resolve_triple(triple: RelationTriple, idx: NameIndex) -> RelationTriple:
    """用批内 NameIndex 把 triple 端点的 name: 占位解析为 PK(命中)。

    命中时复制为新的 RelationTriple(避免变更跨批共享对象);未命中保留 name: 卫星。
    """
    sid = triple.subject_id
    if sid.startswith(NAME_SATELLITE_PREFIX) and triple.subject_name:
        sid = idx.resolve(triple.subject_type, triple.subject_name)
    oid = triple.object_id
    if oid.startswith(NAME_SATELLITE_PREFIX) and triple.object_name:
        oid = idx.resolve(triple.object_type, triple.object_name)
    if sid == triple.subject_id and oid == triple.object_id:
        return triple
    return RelationTriple(
        subject_id=sid,
        subject_type=triple.subject_type,
        subject_name=triple.subject_name,
        relation=triple.relation,
        object_id=oid,
        object_type=triple.object_type,
        object_name=triple.object_name,
        evidence=triple.evidence,
        confidence=triple.confidence,
        source_doc_id=triple.source_doc_id,
        method=triple.method,
        extracted_at=triple.extracted_at,
    )


def compute_entity_id(entity_key: dict, attrs: dict) -> str | None:
    """统一计算 entity_id：强键优先 → name 兜底 → None。

    name 可能是 list（如 project 的 name_cn=['M1']，由 _one transform 产出），
    归一为首个元素，避免 entity_id 变成 "name:['M1']" 这种 list repr 破坏 PK。
    """
    for k in _STRONG_KEYS:
        v = entity_key.get(k)
        if v:
            return str(v)
    name = (attrs.get("name_cn") or attrs.get("tech_name_cn")
            or attrs.get("name_en") or attrs.get("tech_name_en"))
    if isinstance(name, list):
        name = name[0] if name else None
    if name:
        nm = str(name)
        # name: 卫星 id 须 URL 安全(详情走 /profile/{type}/{id} 路由)且 ≤ VARCHAR64:
        # 超长(>58,留 "name:" 前缀)截断 + md5 后缀保唯一幂等;非 \w/- 字符
        # (空格/标点等)替换为 _,避免 URL path 挂(中文属 \w 保留)。
        import hashlib, re
        if len(nm) > 58:
            nm = re.sub(r'[^\w-]', '_', nm[:42]) + "_" + hashlib.md5(nm.encode()).hexdigest()[:15]
        else:
            nm = re.sub(r'[^\w-]', '_', nm)
        return f"{NAME_SATELLITE_PREFIX}{nm}"
    return None

# 进程内活跃 profile_type 集合 → 同类型互斥，跨类型并行
_active_types: set[str] = set()


class BatchOrchestrator:
    def __init__(self, *, extractor, resolver, scorer, writer,
                 connections=resolve_dsn, tech_miner=None) -> None:
        self._extractor = extractor
        self._resolver = resolver
        self._scorer = scorer
        self._writer = writer
        self._connections = connections
        # tech_concept 阶段(可选):None → no-op,向后兼容(非 tech 表 / 旧 collector)。
        self._tech_miner = tech_miner

    async def run(self, session: AsyncSession, *, task, source) -> int:
        cfg = source.config_json or {}
        tables: list[str] = cfg.get("table_set", [])
        workers: int = int(cfg.get("workers", 4))
        batch_size: int = int(cfg.get("batch_size", workers * 125))
        mode: str = cfg.get("mode", "structured_only")
        max_rows = cfg.get("max_rows")  # per-run 行数上限(小批量/冒烟); None=不限跑完
        watermark: str | None = WatermarkStore.get(source, WatermarkStore.KEY_WM)

        conn_orm = await session.get(DBConnectionORM, cfg["db_connection_id"])
        dsn = self._connections(conn_orm)

        total_imported = 0
        for table in tables:
            # I1: 未映射表跳过（避免静默拉空 + 浪费 Doris 读）
            if get_mapping(table) is None:
                logger.warning("table_unmapped_skipped", table=table)
                continue
            # C2: watermark last_id 按表命名空间，避免多表 source 互相跳过/覆盖
            wm_key = f"{WatermarkStore.KEY_ID}:{table}"
            last_id = WatermarkStore.get(source, wm_key) or 0
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
                    imported = await self._process_batch(
                        session, task, source, rows, mode, table, last_id)
                    total_imported += imported
                    logger.info("batch_processed", table=table, ptype=ptype,
                                imported=imported, last_id=last_id)
                    if max_rows and total_imported >= max_rows:
                        logger.info("max_rows_cap_hit", table=table,
                                    total_imported=total_imported, max_rows=max_rows)
                        return total_imported
                finally:
                    _active_types.discard(ptype)
        return total_imported

    async def _process_batch(self, session, task, source, rows, mode, table, last_id) -> int:
        # TODO: 并发执行 entity 评分/写入（asyncio.Semaphore(workers)），当前批量较小时顺序执行即可。
        # mode == "content_mine" / "both" 的附件内容挖掘由 ContentMiner 在 collector (T13) 层接入，
        # 这里仅负责结构化抽取路径。
        # resolve 整批（消歧需跨行）— I2: 包裹，失败记录+跳过本批
        try:
            entities = await self._resolver.resolve(rows)
        except Exception as exc:  # noqa: BLE001
            logger.warning("batch_resolve_failed", error=str(exc),
                           source_table=rows[0].get("source_table"))
            await self._writer.record_error(
                session, batch_id=task.id, stage="resolve",
                error_msg=str(exc), source_table=rows[0].get("source_table"),
            )
            await session.commit()
            return 0
        imported = 0
        # GAP2: 批内 NameIndex —— 关系端点解析(PK 对齐 profile 节点)
        # NOTE: NameIndex 是批内作用域 —— 在其他批次(或同一次 run 的其他表)中物化
        # 的实体不会解析,对应关系端点保留为 name: 卫星节点。跨批/跨表解析需持久化
        # (type,name)→PK store(follow-up);此处不应被当作 bug。
        name_index = NameIndex()
        # GAP1: 收集本批结构化关系,稍后统一解析端点+写图
        structured_triples: list[RelationTriple] = []
        for ent in entities:
            # real EntityResolver normalizes to top-level attrs
            attrs = ent["attrs"]
            # I2: 单实体 score 失败不丢整批 → 零分兜底继续写
            try:
                scores = await self._scorer.score(
                    profile_type=ent["profile_type"], attrs=attrs,
                    source_rows=ent.get("source_rows", []),
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("entity_score_failed", error=str(exc))
                await self._writer.record_error(
                    session, batch_id=task.id, stage="score",
                    error_msg=str(exc), source_table=rows[0].get("source_table"),
                )
                scores = {"completeness": 0.0, "veracity_score": 0.0,
                          "timeliness_score": 0.0, "data_as_of": None,
                          "dq_index": 0.0}
            # M4/C1: 强键优先，name 归一 list（project name_cn=['M1']→'name:M1'），
            # 无名实体防静默碰撞 → record_error 跳过
            entity_id = compute_entity_id(ent["entity_key"], attrs)
            if not entity_id:
                logger.warning("entity_no_identity",
                               profile_type=ent["profile_type"])
                await self._writer.record_error(
                    session, batch_id=task.id, stage="identity",
                    error_msg="no strong key and no name for entity",
                    source_table=rows[0].get("source_table"),
                )
                continue
            # GAP2: 入索引 —— 后续关系的 name: 端点能解析到此 PK
            etype = _PT2ET.get(ent["profile_type"])
            if etype is not None:
                name_index.add(etype, entity_id, attrs)
            try:
                await self._writer.write_profile(
                    session, profile_type=ent["profile_type"], entity_id=entity_id,
                    attrs=attrs, scores=scores, method="llm_extract",
                )
                # GAP2: profile 节点写入 Neo4j(必须在关系引用它之前)
                if etype is not None:
                    try:
                        await self._writer.upsert_profile_node(
                            entity_type=etype, entity_id=entity_id, attrs=attrs,
                        )
                    except Exception as exc:  # noqa: BLE001  Neo4j 失败不阻塞 profile 灌库
                        logger.warning("profile_node_upsert_failed",
                                       entity_id=entity_id, error=str(exc))
                # GAP1: 抽结构化关系(用第一条 source_row 的 raw_payload 作为源行)
                if etype is not None and ent.get("source_rows"):
                    src_row = ent["source_rows"][0].get("raw_payload", {})
                    try:
                        structured_triples.extend(extract_structured_relations(
                            table, src_row, entity_id, etype,
                        ))
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("struct_relation_extract_failed",
                                       entity_id=entity_id, error=str(exc))
                imported += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("entity_write_failed", entity_id=entity_id,
                               error=str(exc))
                await self._writer.record_error(
                    session, batch_id=task.id, stage="write",
                    error_msg=str(exc), source_table=rows[0].get("source_table"),
                )
        # tech_concept 阶段(可选):L1 IPC 域 + L2 LLM 抽术语聚类 + 证据 + TECH_CONTAINS 树。
        # 放在 profile 主写之后、结构化关系之前:L2 concept 节点先物化,关系引用才有效。
        if self._tech_miner is not None:
            try:
                # SAVEPOINT: tech_concept 失败只回滚本阶段已 flush 的 L1/L2/evidence 行,
                # 主 profile 写入(flushed-but-not-committed,共享同一 session)存活,
                # 由下方 session.commit() 统一提交。否则半应用的 tech_concept 状态会被
                # 那次 commit 一起落库 → 状态损坏。
                async with session.begin_nested():
                    await self._tech_concept_stage(session, task, table, rows)
            except Exception as exc:  # noqa: BLE001  tech_concept 失败不阻塞主灌库
                logger.warning("tech_concept_stage_failed",
                               source_table=table, error=str(exc))
        # GAP1+GAP2: 结构化关系端点解析(name:→PK) + 写图
        if structured_triples:
            resolved = [resolve_triple(t, name_index) for t in structured_triples]
            try:
                await self._writer.write_relations(resolved)
            except Exception as exc:  # noqa: BLE001  关系写入失败不影响 profile 灌库
                logger.warning("struct_relation_write_failed", error=str(exc))
        # C3: watermark 与 profile 原子提交（在 commit 前 set，崩溃不分歧）
        wm_key = f"{WatermarkStore.KEY_ID}:{table}"
        WatermarkStore.set(source, wm_key, last_id)
        await session.commit()
        task.records_imported = (task.records_imported or 0) + imported
        return imported

    async def _tech_concept_stage(self, session, task, table: str,
                                  rows: list[dict]) -> None:
        """L1 IPC 技术域(零 LLM) + L2 LLM 抽术语聚类 → tech profile + 证据 + TECH_CONTAINS。

        仅对 _TECH_TABLES(专利/论文)生效。L2 用 name_cn 归一(英文术语→中文规范名),
        使 EN "mass spectrometry"(name_cn=质谱法)与 CN "质谱法" 聚到同一 L2 entity_id;
        英文原文 term 保留在 cluster_terms 作 alias/evidence。

        前置条件(self._tech_miner is None 由调用方守卫)。
        """
        from metaprofile.ingest_ods.domain.ipc_taxonomy import (
            name_of, subclass_of,
        )
        from metaprofile.ingest_ods.domain.orm_models import TechEvidenceORM
        from metaprofile.ingest_ods.services.tech_clusterer import (
            cluster_entity_id, normalize_term,
        )
        from metaprofile.ingest_ods.services.tech_relation_builder import (
            build_containment_triples,
        )

        if table not in _TECH_TABLES:
            return

        l1_built: set[str] = set()           # 已建 L1 的 IPC subclass 集合
        l2_concepts: list[dict] = []         # 供 TECH_CONTAINS 建边
        for r in rows:
            payload = r.get("raw_payload", {}) or {}
            title = payload.get("title") or ""
            abstract = payload.get("abstract") or ""
            src_id = str(payload.get("original_id")
                         or r.get("source_id") or "")
            ipc_sub = subclass_of(payload.get("ipc_type"))

            # 1. L1 IPC 技术域(零 LLM,规则回卷)
            if ipc_sub:
                l1_id = f"ipc:{ipc_sub}"
                if ipc_sub not in l1_built:
                    await self._writer.write_profile(
                        session, profile_type="tech", entity_id=l1_id,
                        attrs={
                            "tech_name_cn": name_of(ipc_sub),
                            "tech_name_en": ipc_sub, "tech_summary": "",
                            "current_status": "", "trend": "",
                            "tech_layer": "DOMAIN", "ipc_code": ipc_sub,
                        },
                        scores={
                            "completeness": 0.0, "veracity_score": 0.9,
                            "timeliness_score": 0.5, "data_as_of": None,
                            "dq_index": 0.7,
                        },
                        method="rule_extract",
                    )
                    l1_built.add(ipc_sub)

            # 2. L2 LLM 抽术语 + 聚类(用 name_cn 归一)
            terms = await self._tech_miner.mine(title=title, abstract=abstract)
            seen: set[str] = set()
            for t in terms:
                # ← 英文归一:用中文规范名作 canonical,L2 entity 以 CN 名键化
                canonical = t.name_cn or normalize_term(t.term)
                if not canonical:
                    continue
                cid = cluster_entity_id(canonical)
                if not cid or cid in seen:
                    continue
                seen.add(cid)
                await self._writer.write_profile(
                    session, profile_type="tech", entity_id=cid,
                    attrs={
                        "tech_name_cn": canonical, "tech_name_en": "",
                        "tech_summary": "", "current_status": "", "trend": "",
                        "tech_layer": "CONCEPT", "parent_ipc_code": ipc_sub,
                        "cluster_terms": [t.term],   # 英文原文保留为 alias
                    },
                    # L2 CONCEPT 由 LLM 抽取、未经人工/规则核验,可信度低于规则回卷的
                    # L1 DOMAIN(veracity 0.9 / dq 0.7),故 veracity 0.7 / dq 0.6。
                    scores={
                        "completeness": 0.0, "veracity_score": 0.7,
                        "timeliness_score": 0.5, "data_as_of": None,
                        "dq_index": 0.6,
                    },
                    method="llm_extract",
                )
                l2_concepts.append({
                    "entity_id": cid, "name": canonical,
                    "parent_ipc": ipc_sub,
                })
                session.add(TechEvidenceORM(
                    tech_id=cid, source_doc_id=src_id, source_table=table,
                    snippet=title[:_EVIDENCE_SNIPPET_MAX],
                    confidence=float(t.confidence),
                ))

        # 3. TECH_CONTAINS 树边(L1 域 contains L2 概念)
        if l2_concepts and l1_built:
            trips = build_containment_triples(
                l2_concepts=l2_concepts, l1_subclasses=l1_built,
            )
            if trips:
                await self._writer.write_relations(trips)
        await session.flush()
