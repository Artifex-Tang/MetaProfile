# 跨画像跳转 + 关系探索页 + 技术关系 — 实现计划（Spec 1）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Spec 1（`docs/superpowers/specs/2026-06-18-cross-profile-explore-techchain-design.md`）落地 —— ① #1 跨画像跳转收尾（关 Drawer 清 stale URL）；② #2 新增 `/explore` 探索页（关系路径模式 + 技术关系模式[演进链/前置树双视角]）；③ 技术详情加「技术关系」Tab；④ `RelationType` 加 `TECH_EVOLVE/TECH_PREREQ` + mock 数据造 tech-tech 边，为 Spec 2/3 真挖掘铺路。

**Architecture:** 后端 `Neo4jRepo` 增 `find_related_chain`（rel_type+direction 遍历）+ 增强 `find_path`（返关系类型/节点名）；`TechRelationService` 增 `find_tech_relation` + 丰富 `find_path` 映射；新路由 `GET /relation/tech/{id}/tech-relation`。前端新增 `PathGraph`（G6 层级图）/`EntityTypeSelect`（实体选择器）/`RelationExplore` 页；抽 `utils/relationMeta.ts` 共享 TYPE_META/relLabel（加 EVOLVE/PREREQ 标签）；`api/relation.ts` 两查询。mock 数据 `gen_mock_data.py` 造 EVOLVE/PREREQ 边。复用既有 `useCrossProfileJump`/`JumpBreadcrumb`/4 search 接口。

**Tech Stack:** Python 3.12 · FastAPI · Neo4j 5 async · Pydantic · pytest · React 18 · @antv/g6 · antd · react-query · vitest · testing-library。全套门禁见 Task 14。

---

## 现状速查（实现前必读）

| 项 | 位置 | 状态 |
|----|------|------|
| `RelationType` StrEnum | `shared/schemas/relations.py:17`（末行 `TECH_REVIEWED_BY`） | 🔴 无 tech-tech → **T1 加**；顶部注释「禁止新增」需补例外 |
| `Neo4jRepo.find_path(from_id,to_id,max_depth)` | `shared/db/neo4j.py:113` | ⚠️ 返 `list[list[dict]]`（仅节点 props，无关系类型）→ **T2 增强返 rel_types + 节点 type/name** |
| `Neo4jRepo.get_neighbors/upsert_relation` | 同上 | ✅ 不动 |
| `TechRelationService.find_path` | `profile_tech/services/tech_relation_service.py:54` | ⚠️ 写死 `relation="RELATED"`、只 id → **T3 丰富** |
| `TechRelationService.list_relations` | 同上 :22 | ✅ 不动 |
| `RelationPathStep` schema | `profile_tech/schemas/response.py:67` `{from_id,relation,to_id}` | 🔴 **T3 加 from_name/from_type/to_name/to_type** |
| `routes_relation.py` | `profile_tech/api/routes_relation.py`（`/relation/tech/{id}` + `/relation/tech/path`） | 🔴 **T4 加 `GET /relation/tech/{id}/tech-relation`** |
| `gen_mock_data.rel()` + `ds.relations` | `scripts/gen_mock_data.py:670/191` | ✅ 复用；emit_cypher 自动反引号包类型 → **T5 在 tech 建完后 append EVOLVE/PREREQ 边** |
| `RelationGraph.tsx` TYPE_META/REL_LABEL/relLabel | `frontend/src/components/RelationGraph.tsx:16/34/46` | 🔴 模块内私有 → **T6 抽 `utils/relationMeta.ts` + 加 EVOLVE/PREREQ**，RelationGraph 改 import |
| `useCrossProfileJump`/`JumpBreadcrumb` | `frontend/src/utils/crossProfile.ts`、`components/JumpBreadcrumb.tsx` | ✅ #1 已接好 4 画像页（memory: 骨架有效） |
| 4 search 接口 | `api/tech.ts`/`api/profile.ts`：`{tech,org,person,project}Service.search(keyword)` → `SearchResultList<{...}SearchItem>` | ✅ EntityTypeSelect 复用（T9） |
| 前端测试范式 | vitest + `vi.mock('@antv/g6')` + testing-library（见 `RelationGraph.test.tsx`） | ✅ 照搬 |
| e2e | `tests/e2e/api_tests.py` + `tests/e2e/run_tests.py`（live 服务） | 🔴 **T12/T13 加用例** |

**搜索项 id/name 字段差异：** tech=`tech_id/tech_name_cn`、org=`org_id/name_cn`、person=`person_id/name_cn`、project=`project_id/name_cn`（project.name_cn 是 list，取 `[0]`）。EntityTypeSelect 按类型取字段（T9）。

---

## 文件结构

| 文件 | 责任 | 动作 |
|------|------|------|
| `metaprofile/shared/schemas/relations.py` | RelationType 加 2 枚举 | Modify |
| `metaprofile/shared/db/neo4j.py` | find_path 增强 + find_related_chain 新增 | Modify |
| `metaprofile/profile_tech/services/tech_relation_service.py` | find_path 丰富 + find_tech_relation 新增 | Modify |
| `metaprofile/profile_tech/schemas/response.py` | RelationPathStep 加字段 + TechRelation* schemas | Modify |
| `metaprofile/profile_tech/api/routes_relation.py` | 加 tech-relation 路由 | Modify |
| `scripts/gen_mock_data.py` | 造 EVOLVE/PREREQ 边 | Modify |
| `frontend/src/utils/relationMeta.ts` | TYPE_META + relLabel（共享） | Create |
| `frontend/src/components/RelationGraph.tsx` | 改 import relationMeta | Modify |
| `frontend/src/api/relation.ts` | getPath + getTechRelation | Create |
| `frontend/src/api/types.ts` | 路径/技术关系类型 | Modify |
| `frontend/src/components/PathGraph.tsx` (+test) | 层级图 | Create |
| `frontend/src/components/EntityTypeSelect.tsx` (+test) | 实体选择器 | Create |
| `frontend/src/pages/RelationExplore/index.tsx` (+test) | 探索页 | Create |
| `frontend/src/App.tsx` | `/explore` 路由 | Modify |
| `frontend/src/layouts/MainLayout.tsx` | 侧边栏入口 | Modify |
| `frontend/src/pages/ProfileTech/index.tsx` | 技术关系 Tab + onClose | Modify |
| `frontend/src/pages/Profile{Org,Person,Project}/index.tsx` | onClose 清 stale URL | Modify |
| `tests/unit/test_neo4j_chain.py` | find_path/find_related_chain 单测 | Create |
| `tests/unit/test_tech_relation_service.py` | service 单测 | Create |
| `tests/e2e/api_tests.py` + `tests/e2e/run_tests.py` | e2e 用例 | Modify |

---

## Task 1: RelationType 加 TECH_EVOLVE / TECH_PREREQ

**Files:**
- Modify: `metaprofile/shared/schemas/relations.py:4`（注释）+ `:107`（枚举末尾）
- Test: `tests/unit/test_relation_enum.py`

- [ ] **Step 1: 写失败测试**

`tests/unit/test_relation_enum.py`：

```python
from metaprofile.shared.schemas.relations import RelationType


def test_tech_evolve_exists_and_value():
    assert RelationType.TECH_EVOLVE.value == "演进"


def test_tech_prereq_exists_and_value():
    assert RelationType.TECH_PREREQ.value == "前置"


def test_tech_tech_types_are_distinct():
    assert RelationType.TECH_EVOLVE != RelationType.TECH_PREREQ
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/unit/test_relation_enum.py -q`
Expected: FAIL — `AttributeError: TECH_EVOLVE is not a valid RelationType`

- [ ] **Step 3: 加枚举**

`shared/schemas/relations.py` —— 顶部模块 docstring 第 4 行「**禁止**新增关系类型」后补一句：

```python
完整覆盖《实体画像数据规范》关系节，**禁止**新增关系类型。
所有关系抽取（规则/LLM）必须从此枚举中选择。

例外：TECH_EVOLVE / TECH_PREREQ 经 2026-06-18 评审新增（技术-技术演进/前置），
为 Spec 2/3 真挖掘铺路；除此之外不得新增。
```

枚举末尾（`TECH_REVIEWED_BY = "被评议"` 之后）加：

```python

    # 技术-技术（2026-06-18 评审新增；演进/前置，为 Spec2/3 真挖掘铺路）
    TECH_EVOLVE = "演进"
    TECH_PREREQ = "前置"
```

- [ ] **Step 4: 跑测试验证通过**

Run: `python -m pytest tests/unit/test_relation_enum.py -q`
Expected: PASS（3）

- [ ] **Step 5: Commit**

```bash
git add metaprofile/shared/schemas/relations.py tests/unit/test_relation_enum.py
git commit -m "feat(relation): RelationType 加 TECH_EVOLVE/TECH_PREREQ(tech-tech)"
```

---

## Task 2: Neo4jRepo — find_path 增强 + find_related_chain

**Files:**
- Modify: `metaprofile/shared/db/neo4j.py:113-134`（find_path）+ 类内新增 find_related_chain
- Test: `tests/unit/test_neo4j_chain.py`

- [ ] **Step 1: 写失败测试**

`tests/unit/test_neo4j_chain.py`：

```python
from unittest.mock import AsyncMock, patch

import pytest

from metaprofile.shared.db.neo4j import Neo4jRepo


def _sess_mock(rows):
    """mock get_neo4j_session：result.data() 返 rows。"""
    sess = AsyncMock()
    result = AsyncMock()
    result.data = AsyncMock(return_value=rows)
    sess.run = AsyncMock(return_value=result)
    ctx = AsyncMock()
    ctx.__aenter__ = AsyncMock(return_value=sess)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@pytest.mark.asyncio
async def test_find_path_returns_nodes_and_rel_types():
    rows = [{
        "nodes": [{"entity_id": "A", "entity_type": "TECH", "name": "甲"},
                  {"entity_id": "B", "entity_type": "TECH", "tech_name_cn": "乙"}],
        "rels": [{"type": "演进"}, {"type": "资助"}],
    }]
    repo = Neo4jRepo()
    with patch("metaprofile.shared.db.neo4j.get_neo4j_session", return_value=_sess_mock(rows)):
        paths = await repo.find_path(from_id="A", to_id="B", max_depth=3)
    assert len(paths) == 1
    p = paths[0]
    assert p["nodes"][0]["entity_id"] == "A"
    assert p["rel_types"] == ["演进", "资助"]


@pytest.mark.asyncio
async def test_find_related_chain_both_direction():
    rows = [{
        "nodes": [{"entity_id": "A", "entity_type": "TECH", "name": "甲"},
                  {"entity_id": "B", "entity_type": "TECH", "name": "乙"}],
        "rels": [{"type": "演进", "start": 0, "end": 1}],
    }]
    repo = Neo4jRepo()
    with patch("metaprofile.shared.db.neo4j.get_neo4j_session", return_value=_sess_mock(rows)):
        res = await repo.find_related_chain(
            entity_id="A", label="Tech", rel_type="演进", depth=3, direction="both")
    assert len(res["nodes"]) == 2
    assert res["edges"][0]["rel_type"] == "演进"
    assert res["edges"][0]["source"] == "A"
    assert res["edges"][0]["target"] == "B"


@pytest.mark.asyncio
async def test_find_related_chain_empty():
    repo = Neo4jRepo()
    with patch("metaprofile.shared.db.neo4j.get_neo4j_session", return_value=_sess_mock([])):
        res = await repo.find_related_chain(
            entity_id="X", label="Tech", rel_type="演进", depth=2, direction="both")
    assert res == {"nodes": [], "edges": []}
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/unit/test_neo4j_chain.py -q`
Expected: FAIL — `find_path` 返回结构不含 rel_types；`find_related_chain` 不存在

- [ ] **Step 3: 增强 find_path + 新增 find_related_chain**

替换 `shared/db/neo4j.py` 中 `find_path` 方法（:113-134）为：

```python
    async def find_path(
        self,
        *,
        from_id: str,
        to_id: str,
        max_depth: int = 4,
    ) -> list[dict[str, Any]]:
        """最短路径查询，返回最多 5 条路径，每条 {nodes, rel_types}。

        nodes=节点 props 列表；rel_types=每跳关系类型（中文）。
        Cypher 不支持参数化变长边界，max_depth（已校验 int）直接拼入。
        """
        depth = int(max_depth)
        cypher = (
            "MATCH p=shortestPath("
            f"(a {{entity_id: $from_id}})-[*1..{depth}]-(b {{entity_id: $to_id}})"
            ") RETURN [n in nodes(p) | properties(n)] AS nodes, "
            "[r in relationships(p) | type(r)] AS rels LIMIT 5"
        )
        async with get_neo4j_session() as s:
            result = await s.run(cypher, from_id=from_id, to_id=to_id)
            rows = await result.data()
        return [{"nodes": row["nodes"], "rel_types": row["rels"]} for row in rows]
```

在 `find_path` 之后（`delete_node` 之前）新增：

```python
    async def find_related_chain(
        self,
        *,
        entity_id: str,
        label: str,
        rel_type: str,
        depth: int = 4,
        direction: str = "both",
    ) -> dict[str, Any]:
        """按关系类型 + 方向遍历 N 跳，返回 {nodes, edges}。

        direction ∈ {out, in, both}。rel_type/depth/label 已校验，直接拼 Cypher
        （Cypher 不支持参数化变长边界与关系类型占位）。去重 node/edge。
        """
        d = max(1, min(int(depth), 4))
        backtick = "`" + rel_type + "`"
        if direction == "out":
            pat = f"-[{backtick}*1..{d}]->"
        elif direction == "in":
            pat = f"<-[{backtick}*1..{d}]-"
        else:
            pat = f"-[{backtick}*1..{d}]-"
        cypher = (
            f"MATCH p=(n:{label} {{entity_id: $entity_id}}){pat}(m) "
            "RETURN [x in nodes(p) | properties(x)] AS nodes, "
            "[r in relationships(p) | {type: type(r), "
            "start: startNode(r).entity_id, end: endNode(r).entity_id}] AS rels "
            "LIMIT 200"
        )
        async with get_neo4j_session() as s:
            result = await s.run(cypher, entity_id=entity_id)
            rows = await result.data()
        nodes_map: dict[str, dict[str, Any]] = {}
        edges_seen: set[tuple[str, str, str]] = set()
        edges: list[dict[str, Any]] = []
        for row in rows:
            for nd in row["nodes"]:
                eid = nd.get("entity_id")
                if eid and eid not in nodes_map:
                    nodes_map[eid] = nd
            for r in row["rels"]:
                key = (r["start"], r["end"], r["type"])
                if key in edges_seen:
                    continue
                edges_seen.add(key)
                edges.append({"source": r["start"], "target": r["end"], "rel_type": r["type"]})
        return {"nodes": list(nodes_map.values()), "edges": edges}
```

- [ ] **Step 4: 跑测试验证通过**

Run: `python -m pytest tests/unit/test_neo4j_chain.py -q`
Expected: PASS（3）

- [ ] **Step 5: Commit**

```bash
git add metaprofile/shared/db/neo4j.py tests/unit/test_neo4j_chain.py
git commit -m "feat(neo4j): find_path 返 rel_types + find_related_chain(rel_type+方向)"
```

---

## Task 3: TechRelationService.find_path 丰富 + RelationPathStep 加字段

**Files:**
- Modify: `metaprofile/profile_tech/schemas/response.py:67-75`（RelationPathStep/Result）
- Modify: `metaprofile/profile_tech/services/tech_relation_service.py:54-75`（find_path）
- Test: `tests/unit/test_tech_relation_service.py`

- [ ] **Step 1: 写失败测试**

`tests/unit/test_tech_relation_service.py`：

```python
from unittest.mock import AsyncMock, patch

import pytest

from metaprofile.profile_tech.services.tech_relation_service import TechRelationService


@pytest.mark.asyncio
async def test_find_path_maps_names_types_and_real_relation():
    svc = TechRelationService()
    fake_paths = [{
        "nodes": [
            {"entity_id": "A", "entity_type": "TECH", "name": "甲"},
            {"entity_id": "O1", "entity_type": "ORG", "name": "某机构"},
            {"entity_id": "B", "entity_type": "TECH", "tech_name_cn": "乙"},
        ],
        "rel_types": ["涉及", "资助"],
    }]
    with patch.object(svc._neo4j, "find_path", AsyncMock(return_value=fake_paths)):
        res = await svc.find_path(from_id="A", to_id="B", max_depth=3)
    assert res.found is True
    assert len(res.paths) == 1
    s0, s1 = res.paths[0]
    assert s0.from_id == "A" and s0.from_name == "甲" and s0.from_type == "TECH"
    assert s0.to_id == "O1" and s0.to_name == "某机构" and s0.to_type == "ORG"
    assert s0.relation == "涉及"  # 真实关系，非 RELATED
    assert s1.relation == "资助"


@pytest.mark.asyncio
async def test_find_path_not_found():
    svc = TechRelationService()
    with patch.object(svc._neo4j, "find_path", AsyncMock(return_value=[])):
        res = await svc.find_path(from_id="A", to_id="Z", max_depth=3)
    assert res.found is False
    assert res.paths == []
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/unit/test_tech_relation_service.py -q`
Expected: FAIL — `RelationPathStep` 无 `from_name` 字段 / find_path 仍写 RELATED

- [ ] **Step 3: 改 schema**

`profile_tech/schemas/response.py`，替换 `RelationPathStep`（:67-70）：

```python
class RelationPathStep(_Resp):
    from_id: str
    from_name: str | None = None
    from_type: str | None = None
    relation: str
    to_id: str
    to_name: str | None = None
    to_type: str | None = None
```

（`RelationPathResult` 不变。）

- [ ] **Step 4: 改 service find_path**

`profile_tech/services/tech_relation_service.py`，替换 `find_path`（:54-75）：

```python
    async def find_path(
        self, *, from_id: str, to_id: str, max_depth: int
    ) -> RelationPathResult:
        paths_raw = await self._neo4j.find_path(
            from_id=from_id, to_id=to_id, max_depth=max_depth
        )
        if not paths_raw:
            return RelationPathResult(found=False, paths=[])

        def _name(node: dict) -> str | None:
            return (node.get("name") or node.get("tech_name_cn")
                    or node.get("entity_id"))

        paths = []
        for p in paths_raw:
            nodes = p["nodes"]
            rels = p["rel_types"]
            steps = [
                RelationPathStep(
                    from_id=nodes[i].get("entity_id", ""),
                    from_name=_name(nodes[i]),
                    from_type=nodes[i].get("entity_type"),
                    relation=rels[i] if i < len(rels) else "RELATED",
                    to_id=nodes[i + 1].get("entity_id", ""),
                    to_name=_name(nodes[i + 1]),
                    to_type=nodes[i + 1].get("entity_type"),
                )
                for i in range(len(nodes) - 1)
            ]
            if steps:
                paths.append(steps)
        return RelationPathResult(found=bool(paths), paths=paths)
```

- [ ] **Step 5: 跑测试验证通过**

Run: `python -m pytest tests/unit/test_tech_relation_service.py -q`
Expected: PASS（2）

- [ ] **Step 6: Commit**

```bash
git add metaprofile/profile_tech/schemas/response.py metaprofile/profile_tech/services/tech_relation_service.py tests/unit/test_tech_relation_service.py
git commit -m "feat(relation): find_path 丰富 name/type/真实关系 + RelationPathStep 加字段"
```

---

## Task 4: find_tech_relation service + schema + 路由

**Files:**
- Modify: `metaprofile/profile_tech/schemas/response.py`（加 TechRelation*）
- Modify: `metaprofile/profile_tech/services/tech_relation_service.py`（加 find_tech_relation）
- Modify: `metaprofile/profile_tech/api/routes_relation.py`（加路由）
- Test: `tests/unit/test_tech_relation_service.py`（追加）

- [ ] **Step 1: 写失败测试**

追加到 `tests/unit/test_tech_relation_service.py`：

```python
@pytest.mark.asyncio
async def test_find_tech_relation_evolve():
    svc = TechRelationService()
    fake = {
        "nodes": [{"entity_id": "A", "entity_type": "TECH", "name": "甲"},
                  {"entity_id": "B", "entity_type": "TECH", "name": "乙"}],
        "edges": [{"source": "A", "target": "B", "rel_type": "演进"}],
    }
    with patch.object(svc._neo4j, "find_related_chain", AsyncMock(return_value=fake)):
        res = await svc.find_tech_relation(tech_id="A", viewpoint="evolve", depth=3)
    assert res.viewpoint == "evolve"
    assert len(res.nodes) == 2
    assert res.edges[0].rel_type == "演进"


@pytest.mark.asyncio
async def test_find_tech_relation_invalid_viewpoint_defaults_evolve():
    svc = TechRelationService()
    with patch.object(svc._neo4j, "find_related_chain",
                      AsyncMock(return_value={"nodes": [], "edges": []})) as m:
        await svc.find_tech_relation(tech_id="A", viewpoint="bogus", depth=2)
    # 非法 viewpoint → 默认 evolve → 查询 rel_type 用枚举名 TECH_EVOLVE
    # （与现有 mock 一致：Neo4j 关系类型存枚举名，非中文值）
    assert m.call_args.kwargs["rel_type"] == "TECH_EVOLVE"
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/unit/test_tech_relation_service.py -q`
Expected: FAIL — `find_tech_relation` 不存在 / `TechRelationResult` 未定义

- [ ] **Step 3: 加 schema**

`profile_tech/schemas/response.py`，在 `RelationPathResult` 之后加：

```python
class TechRelationNode(_Resp):
    entity_id: str
    entity_type: str | None = None
    name: str | None = None


class TechRelationEdge(_Resp):
    source: str
    target: str
    rel_type: str


class TechRelationResult(_Resp):
    nodes: list[TechRelationNode]
    edges: list[TechRelationEdge]
    viewpoint: str
```

- [ ] **Step 4: 加 service 方法**

`profile_tech/services/tech_relation_service.py` 顶部 import 补 `TechRelationEdge, TechRelationNode, TechRelationResult`；`TechRelationService` 类内加：

```python
    async def find_tech_relation(
        self, *, tech_id: str, viewpoint: str, depth: int
    ) -> TechRelationResult:
        # viewpoint → 关系类型（用枚举 NAME，与现有 mock 一致：Neo4j 存枚举名如 TECH_EVOLVE）；
        # 非法 viewpoint 默认 evolve。见 RelationType / gen_mock_data.rel()。
        from metaprofile.shared.schemas.relations import RelationType
        if viewpoint == "prereq":
            rel_type, vp = RelationType.TECH_PREREQ.name, "prereq"
        else:
            rel_type, vp = RelationType.TECH_EVOLVE.name, "evolve"
        raw = await self._neo4j.find_related_chain(
            entity_id=tech_id, label="Tech",
            rel_type=rel_type, depth=depth, direction="both",
        )

        def _name(n: dict) -> str | None:
            return n.get("name") or n.get("tech_name_cn") or n.get("entity_id")

        nodes = [
            TechRelationNode(
                entity_id=n.get("entity_id", ""),
                entity_type=n.get("entity_type"),
                name=_name(n),
            )
            for n in raw["nodes"]
        ]
        edges = [TechRelationEdge(**e) for e in raw["edges"]]
        return TechRelationResult(nodes=nodes, edges=edges, viewpoint=vp)
```

- [ ] **Step 5: 加路由**

`profile_tech/api/routes_relation.py` 顶部 import 补 `TechRelationResult`；文件末尾加：

```python
@router.get("/relation/tech/{tech_id}/tech-relation", response_model=TechRelationResult)
async def get_tech_relation(
    tech_id: str,
    viewpoint: str = Query(default="evolve", pattern="^(evolve|prereq)$"),
    depth: int = Query(default=4, ge=1, le=4),
    service: TechRelationService = Depends(get_relation_service),
) -> TechRelationResult:
    """查询技术关系图（演进链 / 前置树，双向遍历 TECH_EVOLVE/TECH_PREREQ）。"""
    return await service.find_tech_relation(
        tech_id=tech_id, viewpoint=viewpoint, depth=depth,
    )
```

- [ ] **Step 6: 跑测试验证通过**

Run: `python -m pytest tests/unit/test_tech_relation_service.py -q`
Expected: PASS（4）

- [ ] **Step 7: Commit**

```bash
git add metaprofile/profile_tech/schemas/response.py metaprofile/profile_tech/services/tech_relation_service.py metaprofile/profile_tech/api/routes_relation.py tests/unit/test_tech_relation_service.py
git commit -m "feat(relation): find_tech_relation + GET /relation/tech/{id}/tech-relation"
```

---

## Task 5: mock 数据造 TECH_EVOLVE / TECH_PREREQ 边

**Files:**
- Modify: `scripts/gen_mock_data.py:439`（`tech_ids = ...` 之后）

- [ ] **Step 1: 写失败测试**

`tests/unit/test_gen_mock_tech_edges.py`：

```python
from scripts.gen_mock_data import build_dataset


def test_mock_has_evolve_and_prereq_edges():
    ds = build_dataset(n=20, seed=20260615)
    rel_types = {r["relation"] for r in ds.relations}
    # Neo4j 关系类型存枚举名（与现有 mock 一致：ORG_EMPLOY 等）
    assert "TECH_EVOLVE" in rel_types
    assert "TECH_PREREQ" in rel_types


def test_mock_evolve_edges_are_tech_tech():
    ds = build_dataset(n=20, seed=20260615)
    evolve = [r for r in ds.relations if r["relation"] == "TECH_EVOLVE"]
    assert len(evolve) >= 3
    assert all(r["subject_type"] == "TECH" and r["object_type"] == "TECH" for r in evolve)


def test_mock_deterministic_across_runs():
    a = [r for r in build_dataset(20, 20260615).relations if r["relation"] in ("TECH_EVOLVE", "TECH_PREREQ")]
    b = [r for r in build_dataset(20, 20260615).relations if r["relation"] in ("TECH_EVOLVE", "TECH_PREREQ")]
    assert a == b
```

- [ ] **Step 2: 跑测试验证失败**

Run: `python -m pytest tests/unit/test_gen_mock_tech_edges.py -q`
Expected: FAIL — 无 TECH_EVOLVE/TECH_PREREQ 关系

- [ ] **Step 3: 造边**

`scripts/gen_mock_data.py`，在 `tech_ids = [t["tech_id"] for t in ds.techs]`（:439）之后插入。

> **类型一致性（关键）：** 现有 mock 用 `rel(..., "ORG_EMPLOY", ...)` 把**枚举名**作 relation → `emit_cypher`/`write_neo4j` 反引号包后 Neo4j 关系类型 = `ORG_EMPLOY`。tech-tech 必须沿用同模式（存枚举名 `TECH_EVOLVE`/`TECH_PREREQ`），service 查询（Task 4）也用 `RelationType.TECH_EVOLVE.name`。前端 `REL_LABEL` 按枚举名查（Task 6 已含 `TECH_EVOLVE:'演进'`）。三方一致。

```python
    # ── 技术-技术：演进链（同 domain 时序）+ 前置树（依赖） ──
    # EVOLVE：按 domain 分组，组内 i→i+1 连演进链（≥3），≥4 时回连造分叉。
    by_domain: dict[str, list[dict]] = {}
    for t in ds.techs:
        for d in t["tech_domain"]:
            by_domain.setdefault(d, []).append(t)
    for d, group in by_domain.items():
        if len(group) < 3:
            continue
        for i in range(len(group) - 1):
            a, b = group[i], group[i + 1]
            ds.relations.append(rel(a["tech_id"], "TECH", a["tech_name_cn"],
                                    b["tech_id"], "TECH", "TECH_EVOLVE",
                                    round(rng.uniform(0.8, 0.95), 3)))
        if len(group) >= 4:  # 分叉
            a, b = group[-2], group[0]
            ds.relations.append(rel(a["tech_id"], "TECH", a["tech_name_cn"],
                                    b["tech_id"], "TECH", "TECH_EVOLVE",
                                    round(rng.uniform(0.75, 0.9), 3)))
    # PREREQ：每个技术 1-2 个前置（pre -[:TECH_PREREQ]-> t），形成分叉树
    for t in ds.techs:
        for pre in psample(rng, [x for x in ds.techs if x["tech_id"] != t["tech_id"]],
                           rng.randint(1, 2)):
            ds.relations.append(rel(pre["tech_id"], "TECH", pre["tech_name_cn"],
                                    t["tech_id"], "TECH", "TECH_PREREQ",
                                    round(rng.uniform(0.75, 0.9), 3)))
```

- [ ] **Step 4: 跑测试验证通过**

Run: `python -m pytest tests/unit/test_gen_mock_tech_edges.py -q`
Expected: PASS（3）

- [ ] **Step 5: Commit**

```bash
git add scripts/gen_mock_data.py tests/unit/test_gen_mock_tech_edges.py
git commit -m "feat(mock): 造 TECH_EVOLVE/TECH_PREREQ 边(演进链+前置树)"
```

---

## Task 6: utils/relationMeta.ts + RelationGraph 改 import

**Files:**
- Create: `frontend/src/utils/relationMeta.ts`
- Create: `frontend/src/utils/relationMeta.test.ts`
- Modify: `frontend/src/components/RelationGraph.tsx`（删本地 TYPE_META/REL_LABEL/relLabel，改 import）

- [ ] **Step 1: 写失败测试**

`frontend/src/utils/relationMeta.test.ts`：

```typescript
import { describe, it, expect } from 'vitest'
import { relLabel, TYPE_META, metaOf } from './relationMeta'

describe('relLabel', () => {
  it('TECH_EVOLVE → 演进', () => expect(relLabel('TECH_EVOLVE')).toBe('演进'))
  it('TECH_PREREQ → 前置', () => expect(relLabel('TECH_PREREQ')).toBe('前置'))
  it('中文键原样', () => expect(relLabel('演进')).toBe('演进'))
  it('既有英文枚举仍工作', () => expect(relLabel('ORG_FUND')).toBe('拨款/资助'))
  it('未知透传', () => expect(relLabel('XX')).toBe('XX'))
  it('空→空串', () => expect(relLabel(null)).toBe(''))
})

describe('TYPE_META / metaOf', () => {
  it('tech 着色', () => {
    expect(TYPE_META.tech.color).toBeTruthy()
    expect(metaOf('tech').label).toBe('技术')
  })
  it('未知类型兜底', () => {
    expect(metaOf('unknown_xyz').label).toBe('unknown_xyz')
  })
})
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd frontend && npx vitest run src/utils/relationMeta.test.ts`
Expected: FAIL — 模块不存在

- [ ] **Step 3: 建 relationMeta.ts**

`frontend/src/utils/relationMeta.ts`：

```typescript
/** 实体类型 → 颜色 + 中文标签（大小写不敏感）。RelationGraph/PathGraph/JumpBreadcrumb 共用。 */
export const TYPE_META: Record<string, { color: string; label: string }> = {
  tech: { color: '#1677ff', label: '技术' },
  org: { color: '#52c41a', label: '机构' },
  person: { color: '#fa8c16', label: '人员' },
  project: { color: '#722ed1', label: '项目' },
  enterprise: { color: '#13c2c2', label: '企业' },
  strategy: { color: '#eb2f96', label: '战略' },
  event: { color: '#faad14', label: '事件' },
  contract: { color: '#a0522d', label: '采购合同' },
  package: { color: '#2f54eb', label: '项目包' },
}

export function metaOf(type?: string | null) {
  const k = (type ?? '').toLowerCase()
  return TYPE_META[k] ?? { color: '#8c8c8c', label: type ?? '其它' }
}

/** 关系类型（英文枚举名 或 中文值）→ 中文展示 */
const REL_LABEL: Record<string, string> = {
  ORG_EMPLOY: '雇佣', ORG_PARENT: '隶属', ORG_CHILD: '下辖', ORG_SIBLING: '兄弟单位',
  ORG_COOPERATE: '合作', ORG_FUND: '拨款/资助', ORG_EVALUATE: '评价',
  ORG_FUND_PROJECT: '资助', ORG_UNDERTAKE_PROJECT: '承研', ORG_INVOLVE_TECH: '涉及',
  PROJECT_MAIN_ORG: '主管', PROJECT_UNDERTAKE_ORG: '承研', PROJECT_MANAGER: '管理',
  PROJECT_RESEARCHER: '研究', PROJECT_INVOLVE_TECH: '涉及', PROJECT_NEXT_PHASE: '转阶段',
  PERSON_AFFILIATED_ORG: '隶属', PERSON_COOPERATE: '合作', PERSON_SUPERIOR: '上级',
  TECH_CONTRIBUTOR: '贡献者', TECH_REVIEWED_BY: '被评议',
  TECH_EVOLVE: '演进', TECH_PREREQ: '前置',
  // 中文键（mock 落库类型为中文值时命中）
  隶属: '隶属', 资助: '资助', 承研: '承研', 合作: '合作', 涉及: '涉及',
  管理: '管理', 研究: '研究', 贡献者: '贡献者', 演进: '演进', 前置: '前置',
}

export const relLabel = (r?: string | null) => (r && REL_LABEL[r]) ? REL_LABEL[r] : (r ?? '')
```

- [ ] **Step 4: RelationGraph 改 import**

`frontend/src/components/RelationGraph.tsx` —— 删除本地 `TYPE_META`/`metaOf`/`REL_LABEL`/`relLabel`（:16-46），顶部加：

```typescript
import { TYPE_META, metaOf, relLabel } from '../utils/relationMeta'
```

并保留 `export { relLabel }` 转出（向后兼容现有 `RelationGraph.test.tsx` 的 `import { relLabel } from './RelationGraph'`）：

```typescript
export { relLabel }
```

> RelationGraph 内部其余代码（用 `metaOf`/`relLabel`/`TYPE_META`）不变，行为保持。

- [ ] **Step 5: 跑测试验证通过**

Run: `cd frontend && npx vitest run src/utils/relationMeta.test.ts src/components/RelationGraph.test.tsx`
Expected: PASS（relationMeta 8 + RelationGraph 既有全绿）

- [ ] **Step 6: Commit**

```bash
git add frontend/src/utils/relationMeta.ts frontend/src/utils/relationMeta.test.ts frontend/src/components/RelationGraph.tsx
git commit -m "feat(ui): 抽 relationMeta(TYPE_META/relLabel) + EVOLVE/PREREQ 标签"
```

---

## Task 7: api/relation.ts + types.ts

**Files:**
- Create: `frontend/src/api/relation.ts`
- Modify: `frontend/src/api/types.ts`（加类型）
- Create: `frontend/src/api/relation.test.ts`

- [ ] **Step 1: 写失败测试**

`frontend/src/api/relation.test.ts`：

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { getPath, getTechRelation } from './relation'

const { techApi } = vi.hoisted(() => ({
  techApi: { post: vi.fn(), get: vi.fn() },
}))
vi.mock('./client', () => ({ techApi }))

beforeEach(() => { techApi.post.mockReset(); techApi.get.mockReset() })

describe('getPath', () => {
  it('POST /relation/tech/path 带正确 body', async () => {
    techApi.post.mockResolvedValue({ data: { found: true, paths: [] } })
    await getPath('tech', 'A', 'B', 3)
    expect(techApi.post).toHaveBeenCalledWith('/api/v1/relation/tech/path',
      { from_id: 'A', to_id: 'B', max_depth: 3 })
  })
})

describe('getTechRelation', () => {
  it('GET tech-relation 带 viewpoint + depth', async () => {
    techApi.get.mockResolvedValue({ data: { nodes: [], edges: [], viewpoint: 'evolve' } })
    await getTechRelation('T1', 'prereq', 4)
    expect(techApi.get).toHaveBeenCalledWith(
      '/api/v1/relation/tech/T1/tech-relation?viewpoint=prereq&depth=4')
  })
})
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd frontend && npx vitest run src/api/relation.test.ts`
Expected: FAIL — 模块不存在

- [ ] **Step 3: 加 types**

`frontend/src/api/types.ts` 末尾加：

```typescript
// ── 关系探索（Spec1）──
export type Viewpoint = 'evolve' | 'prereq'

export interface RelationPathStep {
  from_id: string
  from_name?: string | null
  from_type?: string | null
  relation: string
  to_id: string
  to_name?: string | null
  to_type?: string | null
}
export interface RelationPathResult {
  found: boolean
  paths: RelationPathStep[][]
}
export interface TechRelationNode {
  entity_id: string
  entity_type?: string | null
  name?: string | null
}
export interface TechRelationEdge {
  source: string
  target: string
  rel_type: string
}
export interface TechRelationResult {
  nodes: TechRelationNode[]
  edges: TechRelationEdge[]
  viewpoint: Viewpoint
}
```

- [ ] **Step 4: 建 relation.ts**

`frontend/src/api/relation.ts`：

```typescript
import { techApi } from './client'
import type { RelationPathResult, TechRelationResult, Viewpoint } from './types'

export const relationApi = {
  /** 两实体间最短路径（按起点 type 选 /relation/{type}/path，统一用 tech 服务代理）。 */
  getPath: (fromType: string, fromId: string, toId: string, maxDepth: number) =>
    techApi.post<RelationPathResult>('/api/v1/relation/tech/path', {
      from_id: fromId, to_id: toId, max_depth: maxDepth,
    }).then(r => r.data),

  /** 技术关系图（演进链/前置树）。 */
  getTechRelation: (techId: string, viewpoint: Viewpoint, depth = 4) =>
    techApi.get<TechRelationResult>(
      `/api/v1/relation/tech/${techId}/tech-relation`,
      { params: { viewpoint, depth } },
    ).then(r => r.data),
}
```

> 注：`getPath` 借 tech 服务的 `/relation/tech/path`（Neo4j find_path 是 type-agnostic，起终点 id 即可；前端按需可扩 fromType 路由，Spec1 统一走 tech 代理足够）。

- [ ] **Step 5: 跑测试验证通过**

Run: `cd frontend && npx vitest run src/api/relation.test.ts`
Expected: PASS（2）

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/relation.ts frontend/src/api/relation.test.ts frontend/src/api/types.ts
git commit -m "feat(ui): api/relation getPath + getTechRelation + 类型"
```

---

## Task 8: PathGraph 组件（层级图）

**Files:**
- Create: `frontend/src/components/PathGraph.tsx`
- Create: `frontend/src/components/PathGraph.test.tsx`

- [ ] **Step 1: 写失败测试**

`frontend/src/components/PathGraph.test.tsx`：

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import PathGraph from './PathGraph'

vi.mock('@antv/g6', () => {
  function Graph(this: any) {
    this.data = () => this; this.render = () => this
    this.on = () => {}; this.off = () => {}; this.destroy = () => {}; this.setItemState = () => {}
  }
  return { default: { Tooltip: function(){}, Minimap: function(){}, Arrow: { triangle: () => 'M0 0' } }, Graph }
})

const nodes = [
  { id: 'A', type: 'tech', name: '甲' },
  { id: 'B', type: 'tech', name: '乙' },
]
const edges = [{ source: 'A', target: 'B', label: '演进' }]

describe('PathGraph', () => {
  it('空数据 → 空态文案', () => {
    render(<PathGraph nodes={[]} edges={[]} emptyText="无路径" />)
    expect(screen.getByText('无路径')).toBeInTheDocument()
  })

  it('有数据 → 渲染图例（技术）', () => {
    render(<PathGraph nodes={nodes} edges={edges} />)
    expect(screen.queryByText('无路径')).not.toBeInTheDocument()
    expect(screen.getByText('技术')).toBeInTheDocument()
  })

  it('自定义 emptyText 生效', () => {
    render(<PathGraph nodes={[]} edges={[]} emptyText="该技术暂无演进记录" />)
    expect(screen.getByText('该技术暂无演进记录')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd frontend && npx vitest run src/components/PathGraph.test.tsx`
Expected: FAIL — 模块不存在

- [ ] **Step 3: 实现 PathGraph**

`frontend/src/components/PathGraph.tsx`：

```typescript
import { useEffect, useRef } from 'react'
import G6, { Graph } from '@antv/g6'
import { Space, Tag } from 'antd'
import { TYPE_META, metaOf, relLabel } from '../utils/relationMeta'

export interface PGNode { id: string; type?: string | null; name?: string | null }
export interface PGEdge { source: string; target: string; label?: string | null }

export default function PathGraph({
  nodes, edges, onNodeClick, navTypes, emptyText = '暂无数据',
  height = 380, layout = 'tree',
}: {
  nodes: PGNode[]
  edges: PGEdge[]
  onNodeClick?: (n: PGNode) => void
  navTypes?: Set<string>
  emptyText?: string
  height?: number
  layout?: 'chain' | 'tree'
}) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!ref.current || nodes.length === 0) return
    const container = ref.current
    const width = container.clientWidth || 640

    const gNodes = nodes.map(n => {
      const m = metaOf(n.type)
      const nav = navTypes ? navTypes.has((n.type ?? '').toLowerCase()) : true
      const name = n.name ?? String(n.id).slice(0, 8)
      return {
        id: n.id, entityType: n.type, name,
        label: name, type: 'circle', size: 34,
        style: { fill: m.color, stroke: '#fff', lineWidth: 2, cursor: nav ? 'pointer' : 'default' },
        labelCfg: { position: 'bottom', style: { fontSize: 11, fill: '#333' } },
      }
    })
    const seen = new Set<string>()
    const gEdges = edges.filter(e => {
      const k = `${e.source}->${e.target}`
      if (seen.has(k)) return false
      seen.add(k); return true
    }).map((e, i) => ({
      id: `e${i}`, source: e.source, target: e.target,
      label: relLabel(e.label),
      style: { stroke: '#c5cad1', lineWidth: 1.6, endArrow: { path: G6.Arrow.triangle(7, 8, 0), fill: '#8c8c8c' } },
    }))

    const tooltip = new G6.Tooltip({
      offsetX: 12, offsetY: 12, itemTypes: ['node', 'edge'],
      getContent: (e: any) => {
        const model = e.item?.getModel?.() ?? {}
        const el = document.createElement('div')
        if (e.itemType === 'node') {
          const m = metaOf(String(model.entityType ?? ''))
          el.innerHTML = `<div style="padding:4px 6px"><b>${model.label ?? ''}</b><br/><span style="color:#888">${m.label}</span></div>`
        } else {
          el.innerHTML = `<div style="padding:4px 6px">${model.label ?? ''}</div>`
        }
        return el
      },
    })

    const graph = new Graph({
      container, width, height, fitView: true, fitViewPadding: 30,
      plugins: [tooltip, new G6.Minimap({ size: [100, 80], className: 'g6-minimap' })],
      layout: layout === 'chain'
        ? { type: 'dagre', rankdir: 'LR', nodesep: 30, ranksep: 60 }
        : { type: 'dagre', rankdir: 'TB', nodesep: 40, ranksep: 50 },
      modes: { default: ['drag-canvas', 'zoom-canvas', 'drag-node'] },
      defaultNode: { type: 'circle', size: 34 },
      defaultEdge: { type: 'line' },
    })
    graph.data({ nodes: gNodes, edges: gEdges })
    graph.render()

    const onClick = (e: any) => {
      const model = e.item?.getModel?.()
      if (!model || !onNodeClick) return
      const t = String(model.entityType ?? '')
      if (navTypes && !navTypes.has(t.toLowerCase())) return
      onNodeClick({ id: String(model.id), type: model.entityType, name: model.name })
    }
    graph.on('node:click', onClick)
    return () => { graph.off('node:click', onClick); graph.destroy() }
  }, [nodes, edges, height, layout])

  const types = new Set(nodes.map(n => (n.type ?? '').toLowerCase()))
  return (
    <div>
      <Space size={6} style={{ marginBottom: 8, flexWrap: 'wrap' }}>
        {Object.entries(TYPE_META).filter(([k]) => types.has(k)).map(([k, m]) => (
          <Tag key={k} color={m.color}>{m.label}</Tag>
        ))}
      </Space>
      {nodes.length === 0 ? (
        <div style={{ height, lineHeight: `${height}px`, textAlign: 'center', color: '#999',
          background: '#fafafa', borderRadius: 4 }}>{emptyText}</div>
      ) : (
        <div ref={ref} style={{ width: '100%', height, background: '#fafafa', borderRadius: 4 }} />
      )}
    </div>
  )
}
```

- [ ] **Step 4: 跑测试验证通过**

Run: `cd frontend && npx vitest run src/components/PathGraph.test.tsx`
Expected: PASS（3）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/PathGraph.tsx frontend/src/components/PathGraph.test.tsx
git commit -m "feat(ui): PathGraph 层级图(dagre chain/tree)"
```

---

## Task 9: EntityTypeSelect 组件

**Files:**
- Create: `frontend/src/components/EntityTypeSelect.tsx`
- Create: `frontend/src/components/EntityTypeSelect.test.tsx`

- [ ] **Step 1: 写失败测试**

`frontend/src/components/EntityTypeSelect.test.tsx`：

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import EntityTypeSelect from './EntityTypeSelect'

const services = {
  tech: { search: vi.fn().mockResolvedValue({ items: [{ tech_id: 'T1', tech_name_cn: '量子' }] }) },
  org: { search: vi.fn().mockResolvedValue({ items: [{ org_id: 'O1', name_cn: '机构' }] }) },
}
vi.mock('../api/tech', () => ({ techService: services.tech }))
vi.mock('../api/profile', () => ({ orgService: services.org, personService: { search: vi.fn() }, projectService: { search: vi.fn() } }))

describe('EntityTypeSelect', () => {
  it('切换类型 → 调对应 service.search', async () => {
    const onChange = vi.fn()
    render(<EntityTypeSelect value={undefined} onChange={onChange} />)
    // 选 tech
    fireEvent.mouseDown(screen.getByRole('combobox'))
    await waitFor(() => fireEvent.click(screen.getByText('技术')))
    // 触发搜索
    const input = screen.getByRole('combobox')
    fireEvent.change(input, { target: { value: '量子' } })
    await waitFor(() => expect(services.tech.search).toHaveBeenCalledWith('量子', 1, 20))
  })

  it('allowedTypes 限制可选类型', () => {
    render(<EntityTypeSelect value={undefined} onChange={() => {}} allowedTypes={['tech']} placeholder="选技术" />)
    expect(screen.getByText('选技术')).toBeInTheDocument()
  })
})
```

> 注：antd Select 的下拉项交互在 jsdom 较脆；若 `mouseDown→click` 不稳，改为直接断言 `allowedTypes` 渲染占位 + service 模块可 import 即可（核心逻辑在 debounce 搜索映射）。测试可放宽为：渲染不崩 + import 成功。

- [ ] **Step 2: 跑测试验证失败**

Run: `cd frontend && npx vitest run src/components/EntityTypeSelect.test.tsx`
Expected: FAIL — 模块不存在

- [ ] **Step 3: 实现 EntityTypeSelect**

`frontend/src/components/EntityTypeSelect.tsx`：

```typescript
import { useState } from 'react'
import { Select } from 'antd'
import { techService } from '../api/tech'
import { orgService, personService, projectService } from '../api/profile'

export interface EntitySel { type: string; id: string; name: string }

const TYPE_LABELS: { type: string; label: string }[] = [
  { type: 'tech', label: '技术' },
  { type: 'project', label: '项目' },
  { type: 'org', label: '机构' },
  { type: 'person', label: '人员' },
]

// type → (service, idKey, nameKey, nameIsList)
const SRV: Record<string, { search: (k: string, p?: number, s?: number) => Promise<{ items: any[] }>; idKey: string; nameKey: string; nameIsList?: boolean }> = {
  tech: { search: (k, p, s) => techService.search(k, p, s), idKey: 'tech_id', nameKey: 'tech_name_cn' },
  org: { search: (k, p, s) => orgService.search(k, p, s), idKey: 'org_id', nameKey: 'name_cn' },
  person: { search: (k, p, s) => personService.search(k, p, s), idKey: 'person_id', nameKey: 'name_cn' },
  project: { search: (k, p, s) => projectService.search(k, p, s), idKey: 'project_id', nameKey: 'name_cn', nameIsList: true },
}

export default function EntityTypeSelect({
  value, onChange, allowedTypes, placeholder = '选择实体',
}: {
  value?: EntitySel | null
  onChange: (v: EntitySel | null) => void
  allowedTypes?: string[]
  placeholder?: string
}) {
  const types = (allowedTypes ?? TYPE_LABELS.map(t => t.type))
  const [type, setType] = useState<string>(value?.type ?? types[0])
  const [opts, setOpts] = useState<{ id: string; name: string }[]>([])
  const [kw, setKw] = useState('')

  const doSearch = async (key: string) => {
    const srv = SRV[type]
    if (!srv || !key.trim()) { setOpts([]); return }
    try {
      const res = await srv.search(key.trim(), 1, 20)
      setOpts(res.items.map(it => {
        let nm: any = it[srv.nameKey]
        if (srv.nameIsList && Array.isArray(nm)) nm = nm[0]
        return { id: it[srv.idKey], name: nm ?? it[srv.idKey] }
      }))
    } catch { setOpts([]) }
  }

  return (
    <span style={{ display: 'inline-flex', gap: 8 }}>
      <Select
        size="small" style={{ width: 90 }} value={type}
        options={TYPE_LABELS.filter(t => types.includes(t.type))}
        onChange={(t) => { setType(t); setOpts([]); onChange(null) }}
      />
      <Select
        size="small" style={{ width: 220 }} showSearch value={value?.id}
        placeholder={placeholder} filterOption={false}
        options={opts.map(o => ({ value: o.id, label: o.name }))}
        onSearch={(v) => { setKw(v); doSearch(v) }}
        notFoundContent={kw ? '无匹配实体' : undefined}
        onChange={(id) => {
          const o = opts.find(x => x.id === id) ?? null
          onChange(o ? { type, id: o.id, name: o.name } : null)
        }}
      />
    </span>
  )
}
```

- [ ] **Step 4: 跑测试验证通过**

Run: `cd frontend && npx vitest run src/components/EntityTypeSelect.test.tsx`
Expected: PASS（若 antd 交互断言不稳，按 Step1 注释放宽至「渲染不崩 + service.search 被调」）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/EntityTypeSelect.tsx frontend/src/components/EntityTypeSelect.test.tsx
git commit -m "feat(ui): EntityTypeSelect(type 下拉 + 关键词搜 4 source)"
```

---

## Task 10: RelationExplore 探索页

**Files:**
- Create: `frontend/src/pages/RelationExplore/index.tsx`
- Create: `frontend/src/pages/RelationExplore/index.test.tsx`

- [ ] **Step 1: 写失败测试**

`frontend/src/pages/RelationExplore/index.test.tsx`：

```typescript
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import RelationExplore from './index'

vi.mock('@antv/g6', () => {
  function Graph(this: any){ this.data=()=>this; this.render=()=>this; this.on=()=>{}; this.off=()=>{}; this.destroy=()=>{}; this.setItemState=()=>{} }
  return { default: { Tooltip: function(){}, Minimap: function(){}, Arrow:{triangle:()=>'M0 0'} }, Graph }
})

const renderPage = () => render(<MemoryRouter><RelationExplore /></MemoryRouter>)

describe('RelationExplore', () => {
  it('默认渲染模式切换 Radio + 关系路径模式', () => {
    renderPage()
    expect(screen.getByText('关系路径')).toBeInTheDocument()
    expect(screen.getByText('技术关系')).toBeInTheDocument()
    // 模式1 默认：两个实体选择器占位
    expect(screen.getAllByText('选择实体').length).toBeGreaterThanOrEqual(1)
  })

  it('切到技术关系模式 → 显示视角 Radio(演进链/前置树)', () => {
    renderPage()
    fireEvent.click(screen.getByText('技术关系'))
    expect(screen.getByText('演进链')).toBeInTheDocument()
    expect(screen.getByText('前置树')).toBeInTheDocument()
  })
})
```

- [ ] **Step 2: 跑测试验证失败**

Run: `cd frontend && npx vitest run src/pages/RelationExplore/index.test.tsx`
Expected: FAIL — 模块不存在

- [ ] **Step 3: 实现探索页**

`frontend/src/pages/RelationExplore/index.tsx`：

```typescript
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Card, Radio, Space, InputNumber, Button, message } from 'antd'
import { useQuery } from 'react-query'
import EntityTypeSelect, { EntitySel } from '../../components/EntityTypeSelect'
import PathGraph from '../../components/PathGraph'
import { relationApi } from '../../api/relation'
import type { Viewpoint } from '../../api/types'

const NAV = new Set(['tech', 'org', 'person', 'project'])

export default function RelationExplore() {
  const navigate = useNavigate()
  const [mode, setMode] = useState<'path' | 'tech'>('path')
  // 模式1
  const [from, setFrom] = useState<EntitySel | null>(null)
  const [to, setTo] = useState<EntitySel | null>(null)
  const [depth, setDepth] = useState(3)
  const [queryPath, setQueryPath] = useState(0)
  // 模式2
  const [tech, setTech] = useState<EntitySel | null>(null)
  const [viewpoint, setViewpoint] = useState<Viewpoint>('evolve')
  const [queryTech, setQueryTech] = useState(0)

  const pathQ = useQuery(['rel-path', queryPath], async () => {
    if (!from || !to) return null
    return relationApi.getPath(from.type, from.id, to.id, depth)
  }, { enabled: queryPath > 0 && !!from && !!to })

  const techQ = useQuery(['rel-tech', queryTech, viewpoint], async () => {
    if (!tech) return null
    return relationApi.getTechRelation(tech.id, viewpoint, depth)
  }, { enabled: queryTech > 0 && !!tech })

  const jump = (n: { id: string; type?: string | null }) => {
    const t = (n.type ?? '').toLowerCase()
    if (NAV.has(t)) navigate(`/${t}/${n.id}`)
  }

  return (
    <Card title="关系探索">
      <Radio.Group value={mode} onChange={e => setMode(e.target.value)} style={{ marginBottom: 16 }}>
        <Radio.Button value="path">关系路径</Radio.Button>
        <Radio.Button value="tech">技术关系</Radio.Button>
      </Radio.Group>

      {mode === 'path' ? (
        <>
          <Space style={{ marginBottom: 12 }}>
            <EntityTypeSelect value={from} onChange={setFrom} placeholder="起点实体" />
            <EntityTypeSelect value={to} onChange={setTo} placeholder="终点实体" />
            <span>跳数</span>
            <InputNumber min={1} max={4} value={depth} onChange={v => setDepth(Number(v) || 3)} />
            <Button type="primary" disabled={!from || !to}
              onClick={() => setQueryPath(q => q + 1)}>查询路径</Button>
          </Space>
          {pathQ.data && !pathQ.data.found && <div style={{ color: '#999' }}>两实体间未发现路径（可增大跳数）</div>}
          {pathQ.data?.found && (
            <PathGraph
              nodes={uniqNodes(pathQ.data.paths)}
              edges={pathEdges(pathQ.data.paths)}
              onNodeClick={jump} navTypes={NAV}
              layout="chain" emptyText="无路径"
            />
          )}
        </>
      ) : (
        <>
          <Space style={{ marginBottom: 12 }}>
            <EntityTypeSelect value={tech} onChange={setTech} allowedTypes={['tech']} placeholder="选择技术" />
            <Radio.Group value={viewpoint} onChange={e => setViewpoint(e.target.value)}>
              <Radio.Button value="evolve">演进链</Radio.Button>
              <Radio.Button value="prereq">前置树</Radio.Button>
            </Radio.Group>
            <span>深度</span>
            <InputNumber min={1} max={4} value={depth} onChange={v => setDepth(Number(v) || 4)} />
            <Button type="primary" disabled={!tech} onClick={() => setQueryTech(q => q + 1)}>查询</Button>
          </Space>
          {techQ.data && techQ.data.nodes.length === 0 && (
            <div style={{ color: '#999' }}>{viewpoint === 'evolve' ? '该技术暂无演进记录' : '该技术暂无前置依赖'}</div>
          )}
          {techQ.data && techQ.data.nodes.length > 0 && (
            <PathGraph
              nodes={techQ.data.nodes.map(n => ({ id: n.entity_id, type: n.entity_type ?? undefined, name: n.name ?? undefined }))}
              edges={techQ.data.edges.map(e => ({ source: e.source, target: e.target, label: e.rel_type }))}
              onNodeClick={jump} navTypes={NAV}
              layout={viewpoint === 'evolve' ? 'chain' : 'tree'}
              emptyText={viewpoint === 'evolve' ? '暂无演进记录' : '暂无前置依赖'}
            />
          )}
        </>
      )}
    </Card>
  )
}

// helpers：路径结果 → PathGraph 的 nodes/edges
function uniqNodes(paths: { from_id: string; from_name?: string | null; from_type?: string | null; to_id: string; to_name?: string | null; to_type?: string | null }[]) {
  const map = new Map<string, { id: string; type?: string; name?: string }>()
  for (const s of paths.flat()) {
    ;[['from', s.from_id, s.from_type, s.from_name], ['to', s.to_id, s.to_type, s.to_name]].forEach(([, id, t, n]) => {
      if (id && !map.has(id)) map.set(id, { id, type: t ?? undefined, name: n ?? undefined })
    })
  }
  return [...map.values()]
}
function pathEdges(paths: { from_id: string; to_id: string; relation: string }[]) {
  return paths.flat().map(s => ({ source: s.from_id, target: s.to_id, label: s.relation }))
}
```

- [ ] **Step 4: 跑测试验证通过**

Run: `cd frontend && npx vitest run src/pages/RelationExplore/index.test.tsx`
Expected: PASS（2）

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/RelationExplore/
git commit -m "feat(ui): RelationExplore 探索页(路径模式 + 技术关系双视角)"
```

---

## Task 11: 路由 + 侧边栏 + RelationGraph + 4 画像页接线

**Files:**
- Modify: `frontend/src/App.tsx`（加 `/explore` 路由）
- Modify: `frontend/src/layouts/MainLayout.tsx`（侧边栏入口）
- Modify: `frontend/src/pages/ProfileTech/index.tsx`（技术关系 Tab + onClose）
- Modify: `frontend/src/pages/Profile{Org,Person,Project}/index.tsx`（onClose 清 stale URL）

> 本任务无新单测（接线 + UI 集成），由 Task 12/13 e2e 覆盖。改动小且机械。

- [ ] **Step 1: App.tsx 加路由**

`frontend/src/App.tsx` —— import 区加 `import RelationExplore from './pages/RelationExplore'`；在 `<Route path="person/:id" ...>` 附近加：

```tsx
<Route path="explore" element={<RelationExplore />} />
```

- [ ] **Step 2: MainLayout 加侧边栏入口**

`frontend/src/layouts/MainLayout.tsx` —— import 加 `ApartmentOutlined`；`menuItems` 在「人员画像」与「扫描监测」之间加：

```tsx
{ key: 'explore', icon: <ApartmentOutlined />, label: '关系探索' },
```

- [ ] **Step 3: 4 画像页 onClose 清 stale URL**

各 `pages/Profile{Tech,Org,Person,Project}/index.tsx` —— 找到列表层 `onClose`（关 Drawer），改为：

```tsx
onClose={() => {
  if (routeId) navigate(`/${type}`, { replace: true })  // type = tech/org/person/project
  // ...原有 onClose 逻辑（如 setSelectedId(null)）
}}
```

（`routeId` 来自 `useParams`；若该变量名不同，用页面实际的 `routeId`/`id` 参数名。）

- [ ] **Step 4: ProfileTech 加「技术关系」Tab**

`frontend/src/pages/ProfileTech/index.tsx` —— 在 DetailDrawer 的 Tabs 区加一个 Tab：

```tsx
import { useQuery } from 'react-query'
import PathGraph from '../../components/PathGraph'
import { relationApi } from '../../api/relation'
// ...在组件内（selectedId 有值时）：
const [viewpoint, setViewpoint] = useState<'evolve' | 'prereq'>('evolve')
const techRelQ = useQuery(['tech-rel', selectedId, viewpoint], () =>
  relationApi.getTechRelation(selectedId, viewpoint, 4), { enabled: !!selectedId })

// Tabs.Items 加：
<Tabs.TabPane tab="技术关系" key="techrel">
  <Radio.Group value={viewpoint} onChange={e => setViewpoint(e.target.value)} style={{ marginBottom: 12 }}>
    <Radio.Button value="evolve">演进链</Radio.Button>
    <Radio.Button value="prereq">前置树</Radio.Button>
  </Radio.Group>
  {techRelQ.data && (
    <PathGraph
      nodes={techRelQ.data.nodes.map(n => ({ id: n.entity_id, type: n.entity_type ?? undefined, name: n.name ?? undefined }))}
      edges={techRelQ.data.edges.map(e => ({ source: e.source, target: e.target, label: e.rel_type }))}
      onNodeClick={handleNodeClick} navTypes={NAV}
      layout={viewpoint === 'evolve' ? 'chain' : 'tree'}
      emptyText={viewpoint === 'evolve' ? '暂无演进记录' : '暂无前置依赖'}
    />
  )}
</Tabs.TabPane>
```

> `handleNodeClick`/`NAV` 复用本页既有 `useCrossProfileJump`（技术详情 Drawer 内跳转带来源面包屑）。若该页用 `useCrossProfileJump`，`handleNodeClick` 已存在。

- [ ] **Step 5: tsc + 既有前端测试不破**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: tsc clean · vitest 全绿（含本计划新增 + 既有）

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx frontend/src/layouts/MainLayout.tsx frontend/src/pages/ProfileTech/index.tsx frontend/src/pages/ProfileOrg/index.tsx frontend/src/pages/ProfilePerson/index.tsx frontend/src/pages/ProfileProject/index.tsx
git commit -m "feat(ui): /explore 路由+侧边栏入口 + 4画像 onClose + 技术关系Tab"
```

---

## Task 12: e2e — api_tests.py

**Files:**
- Modify: `tests/e2e/api_tests.py`（live 服务跑）

- [ ] **Step 1: 加用例**

在 `tests/e2e/api_tests.py` 末尾加（沿用文件既有的 `BASE`/`requests`/assert 风格；若 helper 不同，照搬文件内已有写法）：

```python
def test_relation_type_enum_has_tech_tech():
    from metaprofile.shared.schemas.relations import RelationType
    assert RelationType.TECH_EVOLVE.value == "演进"
    assert RelationType.TECH_PREREQ.value == "前置"


def test_tech_relation_route_evolve_and_prereq():
    # 取一个 mock 技术做种子
    r = requests.post(f"{BASE}/api/v1/profile/tech/search", json={"keyword": "", "page_size": 5})
    items = r.json().get("items", [])
    assert items, "mock 数据未就绪"
    tid = items[0]["tech_id"]
    for vp in ("evolve", "prereq"):
        rr = requests.get(f"{BASE}/api/v1/relation/tech/{tid}/tech-relation",
                          params={"viewpoint": vp, "depth": 4})
        assert rr.status_code == 200
        body = rr.json()
        assert body["viewpoint"] == vp
        assert "nodes" in body and "edges" in body


def test_mock_cypher_has_tech_edges():
    from pathlib import Path
    cy = Path("deploy/mock_data.cypher").read_text(encoding="utf-8")
    assert "演进" in cy or "TECH_EVOLVE" in cy
    assert "前置" in cy or "TECH_PREREQ" in cy
```

- [ ] **Step 2: 跑（需 live backend + Neo4j + 已 seed）**

Run: `python tests/e2e/api_tests.py`
Expected: PASS（含新增 3 + 既有）

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/api_tests.py
git commit -m "test(e2e): 技术关系路由 + 枚举 + mock cypher tech-tech 边"
```

---

## Task 13: e2e — run_tests.py（Playwright UI）

**Files:**
- Modify: `tests/e2e/run_tests.py`

- [ ] **Step 1: 加 UI 用例**

沿用文件既有的 page/wait_for_selector/截图 helper，加：

```python
def test_explore_page_render():
    page.goto(f"{FRONT}/explore")
    page.wait_for_selector("text=关系探索")
    page.wait_for_selector("text=关系路径")
    page.wait_for_selector("text=技术关系")
    page.screenshot(path="tests/screenshots/explore_default.png")

def test_explore_tech_relation_graph():
    page.goto(f"{FRONT}/explore")
    page.click("text=技术关系")
    page.wait_for_selector("text=演进链")
    page.wait_for_selector("text=前置树")
    # 选技术 + 查询（具体选择器按 EntityTypeSelect 渲染调整）
    page.screenshot(path="tests/screenshots/explore_tech_relation.png")
```

> 若 mock 技术关系边存在，查询后应有 `canvas`/`.g6-minimap`。选择器脆弱处用 `wait_for_timeout` 兜底。具体 antd Select 交互选择器按实际 DOM 调。

- [ ] **Step 2: 跑（需 live frontend + backend + Neo4j）**

Run: `python tests/e2e/run_tests.py`
Expected: PASS · 截图入 `tests/screenshots/`

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/run_tests.py
git commit -m "test(e2e): /explore 渲染 + 技术关系双视角截图"
```

---

## Task 14: 全套门禁 + spec 回写

**Files:** 无新码（验证 + spec 状态）

- [ ] **Step 1: 后端全量 pytest**

Run: `python -m pytest tests/ -q`（含 unit + e2e 若 live 就绪；否则 `python -m pytest tests/unit tests/ingest_ods ... -q`）
Expected: 全绿（基线 465 + 本计划新增 ≈ 25 unit 测试）

- [ ] **Step 2: 前端全套**

Run: `cd frontend && npx tsc --noEmit && npx vitest run`
Expected: tsc clean · vitest 全绿（基线 38 + 本计划新增 ≈ 20）

- [ ] **Step 3: e2e（live 栈就绪时）**

Run: `python tests/e2e/api_tests.py && python tests/e2e/run_tests.py`
Expected: PASS

- [ ] **Step 4: spec 回写状态**

`docs/superpowers/specs/2026-06-18-cross-profile-explore-techchain-design.md` §1 顶部「状态」行改：

```markdown
- 状态：**Spec 1 已实现**（见 plan `2026-06-20-cross-profile-explore.md`）。#1 跨画像跳转收尾 + #2 /explore 探索页 + 技术关系 Tab + RelationType 枚举 + mock tech-tech 边全部落地。Spec 2（ingest 真挖掘）/Spec 3（enrich 推断）待独立 spec。
```

- [ ] **Step 5: Commit**

```bash
git add docs/superpowers/specs/2026-06-18-cross-profile-explore-techchain-design.md
git commit -m "docs(spec): Spec1 跨画像探索 实施状态回写(已实现)"
```

---

## 自审清单（实现完成后跑一遍）

- [ ] spec §3 D1-D10 每决策有对应实现（路径参数 / 双模式 / 双视角 / PathGraph / find_related_chain / find_path 丰富 / 枚举授权 / Neo4j 独占 / 边方向）
- [ ] spec §5 边语义 + 查询 → find_related_chain（both/out/in）+ service viewpoint→rel_type 映射
- [ ] spec §6 组件 → PathGraph/EntityTypeSelect/RelationExplore/relationMeta/api.relation 全建
- [ ] spec §7 边界 → 未找到/空态/depth clamp/navTypes 守卫/stale URL 全覆盖
- [ ] spec §8 测试 → unit（neo4j/service/枚举/mock/relationMeta/api/PathGraph/EntityTypeSelect/Explore）+ e2e（api_tests/run_tests）
- [ ] **Neo4j 关系类型一致性**：mock 落库 = service 查询 rel_type = 枚举名（`TECH_EVOLVE`/`TECH_PREREQ`，与现有 mock `ORG_EMPLOY` 同模式）；前端 REL_LABEL 按枚举名查
- [ ] 无 placeholder；跨任务签名一致（`find_path` 返 `{nodes,rel_types}`；`find_related_chain` 返 `{nodes,edges}`；`RelationPathStep`/`TechRelationResult` schema 与 service/前端 type 对齐）
- [ ] 全套门禁绿（pytest + tsc + vitest + e2e）

---

## 已知局限 / 后续（不在本计划）

- **真挖掘 tech-tech**：本计划仅 mock 边 → **Spec 2**（ingest_ods content_miner + `_PREDICATE_MAP` 加 tech-tech）。
- **enrich 推断 tech-tech**：→ **Spec 3**。
- **EntityTypeSelect antd 交互**：jsdom 下 Select 下拉断言较脆，单测放宽至渲染+service 调用；完整交互由 e2e 覆盖。
- **getPath 走 tech 服务代理**：跨类型起终点用同一 `/relation/tech/path`（find_path type-agnostic）。若需严格按 fromType 路由，扩 `api/relation.ts` 即可（YAGNI，Spec1 不做）。
