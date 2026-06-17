from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from metaprofile.ingest_ods.services.writer import Writer


@pytest.mark.asyncio
async def test_write_profile_creates_new_org() -> None:
    session = AsyncMock()
    # 不存在现有 → create
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    w = Writer()
    pid = await w.write_profile(
        session,
        profile_type="org",
        entity_id="ORG_1",
        attrs={"name_cn": "甲", "name_en": "A", "summary": "s", "country": "CN",
               "org_types": [], "nature": "企业", "function": "f", "tech_domains": []},
        scores={"veracity_score": 0.8, "timeliness_score": 0.5, "data_as_of": None},
        method="llm_extract",
    )
    assert pid == "ORG_1"
    assert session.add.call_count >= 2  # ORM + changelog
    await session.flush()


@pytest.mark.asyncio
async def test_write_relations_delegates_to_triple_writer() -> None:
    tw = AsyncMock()
    w = Writer(triple_writer=tw)
    await w.write_relations([{"relation": "PERSON_AFFILIATED_ORG"}])
    tw.write_batch.assert_awaited_once()


@pytest.mark.asyncio
async def test_write_relations_ensures_satellite_nodes_before_write() -> None:
    """Regression: Neo4j upsert_relation 是 MATCH 基 —— name: 卫星端点必须在
    写边之前 ensure,否则 MATCH 返回空、MERGE 不建边也不报错,边被静默丢弃。

    用真 Writer + 真 TripleWriter + mock FoundationNeo4jRepo 验证:
      (a) name: 卫星端点(张三)在写边前被 upsert_entity_node ensure;
      (b) PK 端点(ORG_1)不在此重复 ensure(已由 upsert_profile_node 处理);
      (c) upsert_relation 收到两个端点 id("ORG_1" 与 "name:张三")。
    """
    from metaprofile.foundation.relation.triple_writer import TripleWriter
    from metaprofile.ingest_ods.domain.relation_rules import NAME_SATELLITE_PREFIX
    from metaprofile.shared.schemas.base import EntityType, SourceMethod
    from metaprofile.shared.schemas.relations import RelationTriple, RelationType

    # FoundationNeo4jRepo:upsert_entity_node 直接异步;upsert_relation 在 _repo 上。
    neo4j = AsyncMock()
    neo4j._repo.upsert_relation = AsyncMock()

    tw = TripleWriter(neo4j)
    w = Writer(triple_writer=tw, neo4j_repo=neo4j)

    tri = RelationTriple(
        subject_id="ORG_1",
        subject_type=EntityType.ORG,
        subject_name="甲公司",
        relation=RelationType.ORG_EMPLOY,
        object_id=f"{NAME_SATELLITE_PREFIX}张三",
        object_type=EntityType.PERSON,
        object_name="张三",
        confidence=1.0,
        method=SourceMethod.RULE,
        extracted_at=datetime.now(timezone.utc),
    )
    await w.write_relations([tri])

    # (a) 卫星节点(张三) MUST 在写边前被 ensure
    neo4j.upsert_entity_node.assert_any_call(
        EntityType.PERSON,
        f"{NAME_SATELLITE_PREFIX}张三",
        {"name_cn": "张三"},
    )
    # (c) upsert_relation 收到双端点(PK ORG_1 + 卫星 name:张三)
    neo4j._repo.upsert_relation.assert_awaited_once()
    kwargs = neo4j._repo.upsert_relation.await_args.kwargs
    assert kwargs["from_id"] == "ORG_1"
    assert kwargs["to_id"] == f"{NAME_SATELLITE_PREFIX}张三"
    # (b) PK 端点(ORG_1)不应被 ensure(只 ensure name: 卫星)
    pk_ensures = [
        c for c in neo4j.upsert_entity_node.call_args_list
        if c.args and len(c.args) > 1 and c.args[1] == "ORG_1"
    ]
    assert pk_ensures == []


@pytest.mark.asyncio
async def test_write_profile_updates_existing_org() -> None:
    """I1: update 分支应捕获 old_value + 写 changelog。"""
    existing = MagicMock()
    existing.name_cn = "old"
    existing.name_en = "old_en"
    existing.country = "CN"
    existing.summary = "s"
    existing.org_types = []
    existing.nature = "企业"
    existing.function = "f"
    existing.tech_domains = []
    # 评分列
    existing.veracity_score = 0.0
    existing.timeliness_score = 0.0
    existing.data_as_of = None

    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing))
    )
    w = Writer()
    pid = await w.write_profile(
        session,
        profile_type="org",
        entity_id="ORG_1",
        attrs={"name_cn": "new", "name_en": "old_en", "country": "CN",
               "summary": "s", "org_types": [], "nature": "企业",
               "function": "f", "tech_domains": []},
        scores={"veracity_score": 0.9, "timeliness_score": 0.5, "data_as_of": None},
        method="llm_extract",
    )
    assert pid == "ORG_1"
    # name_cn 变更应触发 setattr
    assert any(call.args and call.args[0] is existing for call in session.add.call_args_list) is False  # update 分支不 add orm
    # changelog 已加入，且 old_value 捕获到 name_cn 旧值
    cl_calls = [
        c for c in session.add.call_args_list
        if c.args and getattr(c.args[0], "old_value", None) is not None
    ]
    assert cl_calls, "应至少有一条带 old_value 的 changelog"
    changelog = cl_calls[0].args[0]
    assert changelog.old_value.get("name_cn") == "old"
    assert changelog.new_value["action"] == "ingest_update"
    assert "name_cn" in changelog.new_value["fields"]
    await session.flush()


@pytest.mark.asyncio
async def test_write_profile_creates_project() -> None:
    """project 派发 + 默认值（覆盖 C1：project_no 默认 0 不再 UNIQUE 冲突）。"""
    session = AsyncMock()
    session.execute = AsyncMock(
        return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))
    )
    w = Writer()
    pid = await w.write_profile(
        session,
        profile_type="project",
        entity_id="PRJ_1",
        attrs={"name_cn": ["甲"], "name_en": ["A"], "tech_domain": [],
               "main_orgs": [], "research_content": [], "progress": []},
        scores={"veracity_score": 0.7, "timeliness_score": 0.4, "data_as_of": None},
        method="llm_extract",
    )
    assert pid == "PRJ_1"
    # ORM + changelog ≥ 2
    assert session.add.call_count >= 2
    # 第一个 add 应是 ProjectProfileORM，project_no 默认 0
    orm_arg = session.add.call_args_list[0].args[0]
    assert orm_arg.project_id == "PRJ_1"
    assert orm_arg.project_no == 0
    await session.flush()
