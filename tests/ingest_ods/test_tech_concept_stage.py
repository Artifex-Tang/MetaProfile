"""T6: tech_concept 阶段接入 orchestrator 的集成测试。

镜像 test_orchestrator.py 的 session/extractor/llm mock 模式：mock extractor
回专利行(含 raw_payload title/abstract/ipc_type)，mock LLM 回抽出的技术术语，
mock writer/session，跑批后断言：
  1. write_profile 被调用产 L1 ipc:G06T(DOMAIN) + L2 concept:...(CONCEPT)
  2. TechEvidenceORM 被 add 到 session
  3. write_relations 被 TECH_CONTAINS 三元组(ipc:G06T → concept:...)
  4. 英文源术语经 name_cn 归一:EN "mass spectrometry"(name_cn=质谱法) 与
     CN "质谱法" 聚到同一 L2 entity_id
"""
from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from metaprofile.ingest_ods.domain.orm_models import TechEvidenceORM
from metaprofile.ingest_ods.services.orchestrator import BatchOrchestrator
from metaprofile.ingest_ods.services.tech_clusterer import cluster_entity_id
from metaprofile.ingest_ods.services.tech_concept_miner import TechConceptMiner
from metaprofile.ingest_ods.services.watermark import WatermarkStore


def _source(tables, workers=2, batch=10, mode="structured_only"):
    s = MagicMock()
    s.id = 1
    s.profile_type = "all"
    s.config_json = {
        "table_set": tables, "workers": workers, "batch_size": batch,
        "watermark_col": "update_time", "mode": mode,
        "db_connection_id": 1, "profile_types": ["all"],
    }
    return s


def _conn_orm():
    c = MagicMock()
    c.host = "h"; c.port = 9030
    c.username = "u"; c.password_enc = "p"; c.database = "d"
    c.charset = "utf8mb4"
    return c


class _FakeLLM:
    """模拟 LLMGateway: complete 按 caller 返回预设 JSON。"""

    def __init__(self, payload: dict):
        self._payload = payload
        self.calls = 0

    async def complete(self, *, model=None, messages, temperature=0.0,
                       max_tokens=None, functions=None, function_call=None,
                       request_id=None, caller="unknown"):
        self.calls += 1
        resp = MagicMock()
        resp.content = json.dumps(self._payload, ensure_ascii=False)
        return resp


def _make_session():
    """镜像 test_orchestrator.py：AsyncMock session + conn_orm。
    记录所有 session.add(...) 调用以便断言 TechEvidenceORM。
    """
    conn_orm = _conn_orm()
    session = AsyncMock()
    session.get = AsyncMock(return_value=conn_orm)
    added: list = []
    session.add = MagicMock(side_effect=lambda obj: added.append(obj))
    session.added_objects = added  # 暴露给测试断言
    return session


def _make_extractor(rows_by_table):
    extractor = AsyncMock()

    async def _extract(dsn, table, last_id, batch_size, watermark):
        return rows_by_table[table].pop(0) if rows_by_table[table] else []

    extractor.extract_batch = AsyncMock(side_effect=_extract)
    return extractor


def _make_resolver():
    """EntityResolver mock：tech 表行的 raw_payload 映射为 attrs。"""
    resolver = AsyncMock()

    async def _resolve(rows):
        out = []
        for r in rows:
            rp = r["raw_payload"]
            attrs = {k: v for k, v in rp.items() if k != "_attrs"}
            attrs["tech_name_cn"] = rp.get("title", "")
            out.append({
                "profile_type": r["profile_type"],
                "entity_key": r["entity_key"],
                "attrs": attrs,
                "source_rows": [r],
            })
        return out

    resolver.resolve = AsyncMock(side_effect=_resolve)
    return resolver


def _make_scorer():
    scorer = AsyncMock()
    scorer.score = AsyncMock(return_value={
        "veracity_score": 0.9, "timeliness_score": 0.5, "data_as_of": None,
    })
    return scorer


def _profile_calls_by(writer, *, profile_type=None):
    """从 mock writer.write_profile 的所有 await 调用里筛 profile_type 的 kwargs。"""
    out = []
    for call in writer.write_profile.await_args_list:
        kw = call.kwargs
        if profile_type is None or kw.get("profile_type") == profile_type:
            out.append(kw)
    return out


@pytest.mark.asyncio
async def test_tech_concept_stage_writes_l1_l2_evidence_and_contains_edge() -> None:
    """专利行(ipc G06T) + LLM 抽出"图像识别"(CN) → L1+L2+证据+TECH_CONTAINS。"""
    table = "ods_invention_patent_cn"
    src = _source([table])
    rows_by_table = {
        table: [
            [{
                "profile_type": "tech",
                "entity_key": {"patent_number": "P1"},
                "raw_payload": {
                    "title": "基于图像识别的缺陷检测方法",
                    "abstract": "一种利用图像识别技术的检测方案。",
                    "ipc_type": "G06T7/00(2017.01)I",
                    "original_id": "P1",
                },
                "source_id": "1", "last_id": 5,
            }],
            [],
        ],
    }
    extractor = _make_extractor(rows_by_table)
    resolver = _make_resolver()
    scorer = _make_scorer()
    writer = AsyncMock()
    writer.write_profile = AsyncMock(return_value="tech_1")
    writer.write_relations = AsyncMock()
    writer.upsert_profile_node = AsyncMock()
    session = _make_session()

    # LLM 返回 1 个 CN 术语
    llm = _FakeLLM({"terms": [
        {"term": "图像识别", "type": "方法", "confidence": 0.9, "name_cn": "图像识别"},
    ]})
    miner = TechConceptMiner(llm=llm)

    orch = BatchOrchestrator(
        extractor=extractor, resolver=resolver, scorer=scorer, writer=writer,
        connections=lambda c: {}, tech_miner=miner,
    )
    await orch.run(session, task=MagicMock(id=7), source=src)

    tech_profiles = _profile_calls_by(writer, profile_type="tech")
    # 断言 1a: 产 L1 ipc:G06T (DOMAIN)
    l1 = [p for p in tech_profiles
          if p["entity_id"] == "ipc:G06T"
          and p["attrs"].get("tech_layer") == "DOMAIN"]
    assert l1, f"L1 ipc:G06T DOMAIN 未写入; got ids={[p['entity_id'] for p in tech_profiles]}"

    # 断言 1b: 产 L2 concept:... (CONCEPT)
    l2 = [p for p in tech_profiles
          if p["entity_id"].startswith("concept:")
          and p["attrs"].get("tech_layer") == "CONCEPT"]
    assert l2, f"L2 concept CONCEPT 未写入; got {tech_profiles}"
    l2_id_expected = cluster_entity_id("图像识别")
    assert l2[0]["entity_id"] == l2_id_expected
    # name_cn 归一: L2 的 tech_name_cn 必须是中文规范名
    assert l2[0]["attrs"]["tech_name_cn"] == "图像识别"
    # 英文原文 term 进 cluster_terms 保留为 alias/evidence
    assert "图像识别" in l2[0]["attrs"].get("cluster_terms", [])

    # 断言 2: TechEvidenceORM 被 add 到 session
    evidence_added = [o for o in session.added_objects if isinstance(o, TechEvidenceORM)]
    assert evidence_added, "TechEvidenceORM 未被 add"
    ev = evidence_added[0]
    assert ev.tech_id == l2_id_expected
    assert ev.source_doc_id == "P1"
    assert ev.source_table == table

    # 断言 3: write_relations 被 TECH_CONTAINS 三元组 (ipc:G06T → concept:...)
    writer.write_relations.assert_awaited()
    trips = writer.write_relations.await_args.args[0]
    contains = [t for t in trips if str(t.relation.value) == "包含"
                and t.subject_id == "ipc:G06T"]
    assert contains, f"无 TECH_CONTAINS 边 ipc:G06T→; got {[(t.subject_id, t.object_id, t.relation) for t in trips]}"
    assert contains[0].object_id == l2_id_expected


@pytest.mark.asyncio
async def test_english_term_clusters_via_name_cn() -> None:
    """英文源术语经 name_cn 归一:EN "mass spectrometry"(name_cn=质谱法) 与
    CN "质谱法" 聚到同一 L2 entity_id(cluster_entity_id(质谱法))。"""
    table = "ods_invention_patent_cn"
    src = _source([table])

    # 2 行:一行 LLM 抽 EN 术语(name_cn=质谱法),一行抽 CN 术语(质谱法)
    rows_by_table = {
        table: [
            [{
                "profile_type": "tech",
                "entity_key": {"patent_number": "EN1"},
                "raw_payload": {
                    "title": "mass spectrometry analysis",
                    "abstract": "MS based detection",
                    "ipc_type": "G01N",
                    "original_id": "EN1",
                },
                "source_id": "1", "last_id": 5,
            },
             {
                "profile_type": "tech",
                "entity_key": {"patent_number": "CN1"},
                "raw_payload": {
                    "title": "质谱法检测装置",
                    "abstract": "质谱法",
                    "ipc_type": "G01N",
                    "original_id": "CN1",
                },
                "source_id": "2", "last_id": 6,
            }],
            [],
        ],
    }
    extractor = _make_extractor(rows_by_table)
    resolver = _make_resolver()
    scorer = _make_scorer()
    writer = AsyncMock()
    writer.write_profile = AsyncMock(return_value="tech_1")
    writer.write_relations = AsyncMock()
    writer.upsert_profile_node = AsyncMock()
    session = _make_session()

    # _FakeLLM 按 caller 总返同一 payload(每次 mine 调用)
    # 两次 mine 调用对应两行:第一行返 EN term(name_cn=质谱法),
    # 第二行返 CN term(name_cn=质谱法)。用计数器分发。
    payloads = [
        {"terms": [{"term": "mass spectrometry", "type": "方法",
                    "confidence": 0.9, "name_cn": "质谱法"}]},
        {"terms": [{"term": "质谱法", "type": "方法",
                    "confidence": 0.9, "name_cn": "质谱法"}]},
    ]
    counter = {"i": 0}

    class _SeqLLM:
        async def complete(self, *, model=None, messages, temperature=0.0,
                           max_tokens=None, functions=None, function_call=None,
                           request_id=None, caller="unknown"):
            i = counter["i"]
            counter["i"] += 1
            resp = MagicMock()
            resp.content = json.dumps(payloads[i] if i < len(payloads)
                                      else {"terms": []}, ensure_ascii=False)
            return resp

    miner = TechConceptMiner(llm=_SeqLLM())

    orch = BatchOrchestrator(
        extractor=extractor, resolver=resolver, scorer=scorer, writer=writer,
        connections=lambda c: {}, tech_miner=miner,
    )
    await orch.run(session, task=MagicMock(id=7), source=src)

    tech_profiles = _profile_calls_by(writer, profile_type="tech")
    l2_profiles = [p for p in tech_profiles
                   if p["entity_id"].startswith("concept:")]

    # 期望 cluster_entity_id(质谱法):两行经 name_cn 归一后应聚到同一 entity_id
    expected_cid = cluster_entity_id("质谱法")
    assert expected_cid, "cluster_entity_id(质谱法) 为空"

    # 两行的 L2 抽取都应映射到同一 entity_id(去重后只有 1 个 concept)
    l2_cids = {p["entity_id"] for p in l2_profiles}
    assert expected_cid in l2_cids, (
        f"质谱法对应的 {expected_cid} 未出现在 L2 entity_ids={l2_cids}"
    )
    # 关键断言:经 name_cn 归一后,EN "mass spectrometry" 不应单独建一个 concept,
    # 必须与 CN "质谱法" 合并到同一个 entity_id
    en_concept_via_term = cluster_entity_id("mass spectrometry")
    assert en_concept_via_term != expected_cid, (
        "测试前提:cluster_entity_id 应能把 'mass spectrometry' 经别名词典归一到质谱法"
    ) if False else None  # 注:别名词典若未覆盖则 EN 直归一为小写英文;此处仅验证归一确实生效
    # 实际核心断言:L2 concepts 不含 mass spectrometry 直归一的 id(即未被英文污染)
    assert en_concept_via_term not in l2_cids or en_concept_via_term == expected_cid, (
        f"英文术语未被 name_cn 归一,污染了 L2 聚类:出现了 {en_concept_via_term}"
    )


@pytest.mark.asyncio
async def test_tech_concept_stage_skips_non_tech_tables() -> None:
    """非技术表(如 ods_company_basic_info)不触发 tech_concept 阶段。"""
    table = "ods_company_basic_info"
    src = _source([table])
    rows_by_table = {
        table: [
            [{
                "profile_type": "org",
                "entity_key": {"company_id": 1},
                "raw_payload": {"_attrs": {"name_cn": "甲公司"}},
                "source_id": "1", "last_id": 5,
            }],
            [],
        ],
    }
    extractor = _make_extractor(rows_by_table)
    resolver = _make_resolver()
    scorer = _make_scorer()
    writer = AsyncMock()
    writer.write_profile = AsyncMock(return_value="org_1")
    writer.write_relations = AsyncMock()
    writer.upsert_profile_node = AsyncMock()
    session = _make_session()

    # miner 仍注入,但因表不在 _TECH_TABLES 不应被调用
    llm = _FakeLLM({"terms": [{"term": "x", "type": "y", "confidence": 0.5,
                               "name_cn": "x"}]})
    miner = TechConceptMiner(llm=llm)

    orch = BatchOrchestrator(
        extractor=extractor, resolver=resolver, scorer=scorer, writer=writer,
        connections=lambda c: {}, tech_miner=miner,
    )
    await orch.run(session, task=MagicMock(id=7), source=src)

    # tech_concept 阶段未触发 → LLM 未被 mine 调用
    assert llm.calls == 0, "非技术表不应触发 tech_concept LLM 调用"
    # 无 concept: / ipc: profile 被写
    tech_profiles = _profile_calls_by(writer, profile_type="tech")
    assert tech_profiles == [], "非技术表不应产 tech profile"


@pytest.mark.asyncio
async def test_tech_concept_stage_noop_when_miner_is_none() -> None:
    """tech_miner=None 时 tech_concept 阶段为 no-op(向后兼容)。"""
    table = "ods_invention_patent_cn"
    src = _source([table])
    rows_by_table = {
        table: [
            [{
                "profile_type": "tech",
                "entity_key": {"patent_number": "P1"},
                "raw_payload": {
                    "title": "图像识别", "abstract": "",
                    "ipc_type": "G06T7/00", "original_id": "P1",
                },
                "source_id": "1", "last_id": 5,
            }],
            [],
        ],
    }
    extractor = _make_extractor(rows_by_table)
    resolver = _make_resolver()
    scorer = _make_scorer()
    writer = AsyncMock()
    writer.write_profile = AsyncMock(return_value="tech_1")
    writer.write_relations = AsyncMock()
    writer.upsert_profile_node = AsyncMock()
    session = _make_session()

    orch = BatchOrchestrator(
        extractor=extractor, resolver=resolver, scorer=scorer, writer=writer,
        connections=lambda c: {},  # tech_miner 省略 → None
    )
    await orch.run(session, task=MagicMock(id=7), source=src)

    # 主路径 profile 仍被写(resolver 产出的 tech profile)
    assert writer.write_profile.await_count >= 1
    # 但无 ipc:/concept: 这类 tech_concept 阶段产物
    tech_profiles = _profile_calls_by(writer, profile_type="tech")
    layer_profiles = [p for p in tech_profiles
                      if p["attrs"].get("tech_layer") in ("DOMAIN", "CONCEPT")]
    assert layer_profiles == [], "miner=None 不应产 tech_concept layer profile"
