# 跨画像跳转 + 关系探索页 + 技术（演进/前置）关系 — Spec 1（基础层）

- 日期：2026-06-18
- 分层：**Spec 1 = 基础层**（契约 + UI + mock + 查询，mock 全链路可 demo）。Spec 2（ingest_ods 真挖掘）、Spec 3（enrich worker LLM 推断）为本 spec 的后续独立 spec，见 §11。
- 状态：**Spec 1 已实现**（见 plan `2026-06-20-cross-profile-explore.md`，branch `feat/cross-profile-explore`，E-T1..T14）。#1 跨画像跳转收尾（4 画像 onClose 清 stale URL）+ #2 /explore 探索页（关系路径模式 + 技术关系演进链/前置树双视角）+ 技术详情「技术关系」Tab + RelationType 加 TECH_EVOLVE/TECH_PREREQ + Neo4jRepo find_path 返 rel_types / find_related_chain(rel_type+方向) + mock 造 tech-tech 边。全栈 live e2e 验证通过（后端路由真 Neo4j 遍历 / 前端 Playwright 渲染）。
  - 已知约定：Neo4j 关系类型 mock 落库 = service 查询 = 枚举 **NAME**（TECH_EVOLVE/TECH_PREREQ，与既有 mock ORG_EMPLOY 同模式）；前端 REL_LABEL 按 NAME 查。真挖掘（Spec2 triple-writer）存枚举 **VALUE**（演进/前置）→ Spec2 需归一 NAME vs VALUE。
  - 已知局限：find_path 返 shape 变已迁移 4 画像服务+foundation wrapper；coherence/df_by_source_window presence-vs-count 见弱信号 spec（无关本计划）。
  - Spec 2（ingest_ods 真挖 tech-tech：content_miner + _PREDICATE_MAP）/ Spec 3（enrich LLM 推断 tech-tech）待独立 spec。
- 前置：commit 39be46e，全套绿 API 86 / UI 61 / vitest 38 / tsc clean。

---

## 1. 背景与目标

四个画像（技术/项目/机构/人员）各自独立列表 + 详情 Drawer + 单跳关联图谱；跨画像关联只在 Neo4j，UI 无跨画像钻取、无多跳路径可视化、无技术关系视图。用户诉求：「用业务故事把工具功能串起来 / 技术链怎么体现（界面/功能/数据）」。

**Spec 1 交付：**

1. **跨画像跳转（#1）**：任意画像详情/探索页的关系图谱节点可点击 → 跳该实体对应画像详情，带「来源实体 经「关系」」面包屑回溯。
2. **关系探索页 `/explore`（#2）**：侧边栏新入口，两模式：
   - 模式 1「关系路径」：起点实体 + 终点实体 + 最深跳数 → 多跳最短路径图。
   - 模式 2「技术关系」：选技术 + 视角切换 **演进链（TECH_EVOLVE）/ 前置树（TECH_PREREQ）** → 两种技术关系图。
3. **技术关系 Tab**：技术画像详情加「技术关系」Tab，复用模式 2 组件 + 视角切换。
4. **契约**：`RelationType` 枚举新增 tech-tech 类型（演进/前置），为 Spec 2/3 真挖掘铺路。

业务故事：跟踪某技术 →（演进链看前驱/后继，前置树看依赖）→（探索页路径模式）看承研项目/机构/人员 →（节点跳转）逐层钻取 → 产出选题。

## 2. 现状复核（本会话 grep/read 确认）

### 2.1 已存在（#1 约 90% 接好，前会话骨架）
- `frontend/src/utils/crossProfile.ts`：`useCrossProfileJump(selfType,selfId,selfName)` → `{ctx, handleNodeClick}`；`JumpCtx/NodeClickItem/NAV_TYPES/parseFromQuery`。方案=**路径参数** `navigate('/{type}/{id}?from={selfType}:{selfId}',{state})`。
- `frontend/src/components/JumpBreadcrumb.tsx`（+ test）：依 ctx 渲染面包屑。
- `frontend/src/components/RelationGraph.tsx`：force 星形图，已有 `onNodeClick/navTypes` + `relLabel(r)` 导出。`REL_LABEL` 缺 `TECH_EVOLVE/TECH_PREREQ`。
- 4 画像页全部接好 `useCrossProfileJump + JumpBreadcrumb + RelationGraph onNodeClick + useParams`。
- `App.tsx`：已有 `/tech/:id` `/project/:id` `/org/:id` `/person/:id`。
- 后端 `Neo4jRepo`（`shared/db/neo4j.py`）：`find_path(from_id,to_id,max_depth=4)`（shortestPath，返完整节点 props）、`get_neighbors`、`upsert_relation`。
- 4× `routes_relation.py` 各有 `GET /relation/{type}/{id}`、`POST /relation/{type}/path`（**前端零调用**）。
- 4× `profile_{type}/schemas/response.py` 各自定义 `RelationItem/RelationList/RelationPathStep/RelationPathResult`（重复 4 份）。
- `scripts/gen_mock_data.py`：`rel()`+`ds.relations`+`emit_cypher`（无关系类型白名单，反引号包类型 MERGE 边，自动进 `.cypher` 与实时 loader）。

### 2.2 缺失
- 无 `/explore` 路由/页面/侧边栏。
- `find_path` service 丢节点 name/type（`RelationPathStep` 只 id + 写死 `"RELATED"`）→ 多跳图缺标签。
- 无 tech-tech 边遍历方法；无 `TECH_EVOLVE/PREREQ` 数据与标签。
- **`RelationType` 枚举（`shared/schemas/relations.py`）无 tech-tech 类型**，且注释「禁止新增关系类型」——需明确授权新增（见 §3 D8）。
- #1 收尾：`/{type}/{id}` 关 Drawer 留 stale URL。

### 2.3 关键事实：tech-tech 关系当前**任何地方都没挖**
- `RelationType` 技术 section 仅 `TECH_CONTRIBUTOR`(贡献者)/`TECH_REVIEWED_BY`(被评议)，均 tech↔{person,enterprise}。
- `_PREDICATE_MAP`（`ingest_ods/llm/prompts.py`）零 tech-tech 条目 → LLM 抽到 tech-tech 谓词返 None → 落 RelationStaging 不进 Neo4j。
- `relation_rules.py` tech 表只产 tech↔org/person。
- → Spec 1 用 mock 数据；真挖掘归 Spec 2/3。

### 2.4 与锁定决策的偏离（已采纳）
锁定「方案A 查询参数 `?detail=ID`」，骨架走**路径参数 `/{type}/{id}`**。决策：**保持路径参数**（已 4 页接好、RESTful、可分享、后退键天然生效）。锁定决策据此更新。

## 3. 决策摘要

| # | 决策 | 选择 | 理由 |
|---|---|---|---|
| D1 | 详情 URL 方案 | 路径参数 `/{type}/{id}` | 骨架已接好；避免返工 |
| D2 | /explore 模式 | 路径模式 + 技术关系模式 | 匹配 #1+#2 |
| D3 | 技术关系概念 | **演进链(EVOLVE) + 前置树(PREQ) 双视角** | 用户要两者；同一组件视角切换 |
| D4 | 多跳图渲染 | 新增 `<PathGraph>`（层级/dagre） | 与星形 RelationGraph 职责分离；链/树层级可读 |
| D5 | 实体选择器数据源 | 前端复用 4 search 接口 | 不加后端 |
| D6 | tech-tech 查询 | 新增 `Neo4jRepo.find_related_chain`（rel_type+direction 参数）+ tech 路由 | 一个方法支撑演进/前置两视角 |
| D7 | 路径结果丰富化 | `find_path` 返 rel 类型 + 4 service/schema 补 name/type | 多跳图需标签/名称 |
| D8 | 枚举扩展 | RelationType 加 `TECH_EVOLVE/TECH_PREREQ`，覆盖「禁止新增」 | 真挖掘(Spec2/3)的硬前置；本会话明确授权 |
| D9 | tech-tech 存储 | 仅 Neo4j（不加 typed ORM 表） | 遵循「Neo4j 独占关系」约定 |
| D10 | 边方向语义 | EVOLVE: A→B=A 演进为 B；PREREQ: A→B=A 是 B 的前置 | 见 §6 |

## 4. 架构

```
跨画像跳转(#1):
  RelationGraph/PathGraph node:click → useCrossProfileJump.handleNodeClick
    → navigate('/{type}/{id}?from=...',{state}) → 目标画像 useParams 开 Drawer + JumpBreadcrumb

/explore(#2):
  ─ 模式1 关系路径:
     EntityTypeSelect(起点)+EntityTypeSelect(终点)+depth(1..4)
       → api.relation.getPath(fromType,fromId,toId,depth) → POST /relation/{fromType}/path
       → PathGraph(多跳路径图, node click 跳转)
  ─ 模式2 技术关系:
     EntityTypeSelect(仅tech) + 视角Radio[演进链|前置树] + depth
       → api.relation.getTechRelation(techId,viewpoint,depth)
       → GET /relation/tech/{id}/tech-relation?viewpoint=evolve|prereq&depth=N
       → PathGraph(演进链=线性层级 / 前置树=分叉层级, node click 跳转)

技术关系 Tab(ProfileTech):
  Tab「技术关系」→ 视角Radio + getTechRelation(id,viewpoint) → PathGraph(同模式2)
```

## 5. 边语义与查询（§3 D6/D10 细化）

- **TECH_EVOLVE（演进）**：有向边 `A -[:TECH_EVOLVE]-> B` 表示「A 演进为 B」（A 是 B 的前身/来源）。
  - 演进链视角：从选中技术 X 沿 EVOLVE **双向**遍历（入边=前驱、出边=后继），按时序左→右渲染：`前驱…→ X →…后继`。线性/层级。
- **TECH_PREREQ（前置）**：有向边 `A -[:TECH_PREREQ]-> B` 表示「A 是 B 的前置依赖」（B 需要 A）。
  - 前置树视角：从 X 沿 PREREQ **双向**遍历（入边=X 的前置、出边=依赖 X 的技术），分叉树/DAG。
- **查询方法**：`Neo4jRepo.find_related_chain(entity_id, label, rel_type, depth, direction='both')`
  - direction ∈ {out, in, both}；rel_type 受控（TECH_EVOLVE/TECH_PREREQ）；depth clamp [1,4]。
  - Cypher（both）：`MATCH p=(n:{label}{entity_id:$id})-[:{rel_type}*1..{depth}]-(m) RETURN nodes(p),relationships(p)`（去重）；out/in 用 `->` / `<-` 方向。
  - 返回 `{nodes:[{id,type,name}], edges:[{source,target,rel_type}]}`。
- **路径模式**：复用 `find_path`（跨类型，type-agnostic），前端按**起点 type** 选 `/relation/{fromType}/path`。

## 6. 组件设计

### 6.1 新增前端

**`frontend/src/components/PathGraph.tsx`** — 链/路径/树层级图（G6 dagre/层级）。
- Props：`nodes:{id,type,name}[]`、`edges:{source,target,label?}[]`、`onNodeClick?:(n)=>void`、`navTypes?:Set<string>`、`emptyText?:string`、`layout?:'chain'|'tree'`（chain=线性主导、tree=分叉 dagre；缺省 tree）。
- 行为：节点按 entity_type 着色（共享 TYPE_META，见下）；可跳节点 cursor pointer + hover + click；非 navTypes 不响应；Tooltip 显示名/类型/关系；空数据→空态；nodes/edges 去重。
- 复用：3 处（探索页模式1路径、模式2技术关系、ProfileTech Tab）。

**`frontend/src/components/EntityTypeSelect.tsx`** — 实体选择器。
- Props：`value?:{type,id,name}`、`onChange`、`allowedTypes?:string[]`（模式2 限 `['tech']`）、`placeholder`。
- 行为：type 下拉（技术/项目/机构/人员）+ 关键词搜索（debounce）→ 调对应 `*Service.search(keyword)` → 选项 `{id,name,type}`；空结果「无匹配」。

**`frontend/src/pages/RelationExplore/index.tsx`** — 探索页。
- 顶部 Radio 切「关系路径 / 技术关系」。
- 模式 1：两 `EntityTypeSelect`（起/终）+ depth(1-4) + 查询 → useQuery `getPath` → `<PathGraph layout="chain">`（多路径去重叠加）。
- 模式 2：`EntityTypeSelect`(tech) + 视角 Radio[演进链|前置树] + depth → useQuery `getTechRelation` → `<PathGraph layout={viewpoint==='evolve'?'chain':'tree'}>`。
- 启用条件：必选项齐 + 点查询；`keepPreviousData`。
- **节点 click → 直接 `navigate('/{type}/{id}')`**（探索页非实体详情，**不**走 `useCrossProfileJump`、不显示来源面包屑——因为探索页没有「来源实体」概念）。注：`useCrossProfileJump.handleNodeClick` 内有 `if(!selfId) return` 守卫，故探索页必须用直接 navigate，不能复用该 hook。

**`frontend/src/api/relation.ts`**：
- `getPath(fromType,fromId,toId,maxDepth)` → `POST /api/v1/relation/{fromType}/path` body `{from_id,to_id,max_depth}` → `RelationPathResult`。
- `getTechRelation(techId,viewpoint,maxDepth=4)` → `GET /api/v1/relation/tech/{id}/tech-relation?viewpoint=&depth=` → `TechRelationResult`。
- `api/types.ts` 加：`RelationPathStep`(含 name/type/relation)、`RelationPathResult`、`TechRelationNode/Edge/Result`、`Viewpoint='evolve'|'prereq'`。

**`frontend/src/utils/relationMeta.ts`** — 抽 `TYPE_META`（类型→颜色/中文）+ `relLabel` 自 RelationGraph，供 RelationGraph/PathGraph/JumpBreadcrumb 共用。`REL_LABEL` 加 `TECH_EVOLVE:'演进', TECH_PREREQ:'前置'`。

### 6.2 改前端
- `App.tsx`：`<Route path="explore" element={<RelationExplore/>}>` + import。
- `layouts/MainLayout.tsx`：menuItems 加 `{key:'explore', icon:<ApartmentOutlined/>, label:'关系探索'}`，置「人员画像」与「扫描监测」间。
- `RelationGraph.tsx`：TYPE_META/relLabel 改 import `utils/relationMeta`（行为不变）。
- 4 画像页 `index.tsx`：列表层 `onClose` 当 `routeId` 存在 → `navigate('/{type}',{replace:true})` 清 stale URL；**ProfileTech 加「技术关系」Tab**（视角 Radio + `getTechRelation(id,viewpoint)` → `<PathGraph onNodeClick={handleNodeClick}>`）。

### 6.3 后端
- `shared/schemas/relations.py`：`RelationType` 加
  ```python
  # 技术-技术（本会话授权新增；为 Spec2/3 真挖掘铺路）
  TECH_EVOLVE = "演进"
  TECH_PREREQ = "前置"
  ```
  并把开头「禁止新增关系类型」注释补一句「例外：TECH_EVOLVE/TECH_PREREQ 经 2026-06-18 评审新增」。
- `shared/db/neo4j.py`：
  - 增强 `find_path`：cypher 额外 `relationships(p)` 返每跳关系类型；返回含 rel_types。
  - 新增 `find_related_chain(entity_id, label, rel_type, depth, direction='both')`（见 §5）。
- 4× `services/*_relation_service.py` `find_path`：mapping 补 `from_name/from_type/relation(真实)/to_name/to_type`（node props 取 name/tech_name_cn/entity_type；rel_types 取真实关系）。
- 4× `schemas/response.py` `RelationPathStep`：加 `from_name/from_type/to_name/to_type?:str`（`relation` 改真实类型）。
- `profile_tech/services/tech_relation_service.py`：加 `find_tech_relation(tech_id, viewpoint, depth)` → 调 `find_related_chain(tech_id,'Tech', rel_type, depth, 'both')`，rel_type 按 viewpoint（evolve→TECH_EVOLVE，prereq→TECH_PREREQ）；返 `TechRelationResult{nodes,edges,viewpoint}`。
- `profile_tech/schemas/response.py`：加 `TechRelationNode/Edge/Result`。
- `profile_tech/api/routes_relation.py`：加 `GET /relation/tech/{tech_id}/tech-relation?viewpoint=evolve|prereq&depth=4` → `find_tech_relation`。
- 路由前缀挂 `/api/v1`（与既有 `/relation/tech/{id}` 一致）。

### 6.4 数据（gen_mock_data.py，mock）
- techs 生成后（`tech_ids` 已得），造两类边：
  - **TECH_EVOLVE**：同 domain 内 `tech[i]→tech[i+1]` 连演进（conf 0.8-0.95），每链 ≥3 节点，≥1 分叉。
  - **TECH_PREREQ**：跨/同 domain 造分叉前置依赖（conf 0.75-0.9），形成树（一个技术多前置）。
- 幂等（复用现有 rng/seed）。经 `rel(tid_from,"TECH",cn_from,tid_to,"TECH",cn_to,"TECH_EVOLVE",conf)`+`ds.relations.append` 自动进 `.cypher` 与实时 loader。

## 7. 边界与错误处理

- 路径未找到：`found=false` → PathGraph「两实体间未发现路径（可增大跳数）」。
- 技术关系无边：空态「该技术暂无演进记录」/「暂无前置依赖」（按视角）。
- 选择器 search 空：Select「无匹配实体」。
- depth 越界：后端 clamp [1,4]；前端限 1-4。
- 非 navTypes 节点 click：静默忽略（守卫）。
- stale URL：关 Drawer → `navigate('/{type}',{replace:true})`。
- 多路径/多边叠加：PathGraph 去重后统一画。
- 节点 name 缺失：回退 entity_id 前 8 位（与 RelationGraph 一致）。
- viewpoint 非法：后端默认 evolve（或 422）；前端 Radio 只两值。

## 8. 测试计划

### 8.1 vitest（Dockerfile 含 `npm run test` 门禁）
- `PathGraph`：node click 触发回调；navTypes 外不触发；空态；去重；layout chain/tree。
- `EntityTypeSelect`：type 切换 + debounce + 空结果；allowedTypes。
- `api/relation.ts`：mock fetch 断言 URL/body/解析。
- `utils/relationMeta`：`relLabel('TECH_EVOLVE')==='演进'`、`relLabel('TECH_PREREQ')==='前置'`、TYPE_META 着色。
- `RelationExplore`：模式切换；模式1 两端齐才启用；模式2 仅 tech + 视角切换。
- 既有 `JumpBreadcrumb.test`/`useCrossProfileJump.test` 保持绿。

### 8.2 api_tests（`tests/e2e/api_tests.py`）
- `POST /relation/tech/path`：连通实体→`found=true`，step 含 `from_name/to_name/relation(非 RELATED)`；不连通→`found=false`。
- `GET /relation/tech/{id}/tech-relation?viewpoint=evolve`：返非空 nodes/edges，edges 含 `TECH_EVOLVE`；`viewpoint=prereq` 含 `TECH_PREREQ`。
- `RelationType.TECH_EVOLVE/TECH_PREREQ` 存在断言（import 枚举）。
- mock 数据断言：`deploy/mock_data.cypher` 含 `TECH_EVOLVE` 与 `TECH_PREREQ` 边（grep）。

### 8.3 run_tests（`tests/e2e/run_tests.py`）
- `/explore` 渲染 + 侧边栏入口。
- 模式1：选起/终/深度→路径图 canvas（wait_for_selector）。
- 模式2：选技术→演进链图；切前置树→树图。
- 技术详情「技术关系」Tab：点 Tab→canvas；视角切换。
- 跨画像跳转：drawer 节点 click→URL 变 `/{type}/{id}` + JumpBreadcrumb 可见。
- 截图入 `tests/screenshots/`。

### 8.4 全套门禁
`py -3.12 -m pytest tests/` + `py -3.12 tests/e2e/api_tests.py` + `py -3.12 tests/e2e/run_tests.py` + `cd frontend && npx vitest run` + `tsc`，全绿方完成。

## 9. 关键文件清单

**新增**
- `frontend/src/components/PathGraph.tsx`（+test）、`EntityTypeSelect.tsx`（+test）
- `frontend/src/pages/RelationExplore/index.tsx`
- `frontend/src/api/relation.ts`、`frontend/src/utils/relationMeta.ts`

**改**
- 前端：`App.tsx`、`layouts/MainLayout.tsx`、`components/RelationGraph.tsx`、`utils/crossProfile.ts`（注释）、4×`pages/Profile*/index.tsx`（onClose 回退 + ProfileTech Tab）、`api/types.ts`
- 后端：`shared/schemas/relations.py`（枚举）、`shared/db/neo4j.py`（find_path+find_related_chain）、4×`services/*_relation_service.py`、4×`schemas/response.py`、`profile_tech/services/tech_relation_service.py`、`profile_tech/api/routes_relation.py`、`profile_tech/schemas/response.py`
- 数据：`scripts/gen_mock_data.py`（EVOLVE/PREREQ 边）
- 测试：`tests/e2e/{api_tests,run_tests}.py`、前端各 test

## 10. 非目标（YAGNI，Spec 1 不做）

- **真挖掘 tech-tech 关系** → **Spec 2**（ingest_ods content_miner LLM 从 ODS 附件抽演进/前置 → `_PREDICATE_MAP` 加 tech-tech 条目 → writer 落 Neo4j）。依赖本 spec 的 `TECH_EVOLVE/TECH_PREREQ` 枚举 + 本地 Doris 数据。
- **enrich worker 推断 tech-tech 边** → **Spec 3**（扩 tech enrich：LLM 读 profile 字段推演进/前置边 → Neo4j + EntityChangeLog）。依赖本 spec 枚举。
- 不加 typed ORM 表存技术关系（Neo4j 独占）。
- 不动 ScanMonitor/NewTechDiscovery 图谱。
- 不做统一实体 search 后端（复用 4 search 接口）。
- 不重写路径参数骨架回查询参数。

## 11. 后续 spec（指路，本 spec 不实现）

- **Spec 2**：`docs/superpowers/specs/<date>-tech-relation-ingest-mining-design.md` — ingest_ods 真挖掘。新增 `_PREDICATE_MAP` tech-tech 条目（如 `("演进","tech","tech")→TECH_EVOLVE`、`("前置"/"基于","tech","tech")→TECH_PREREQ`）+ content_miner prompt 抽取 + writer 落边。前提：本地 Doris big3 表 + 附件数据已灌（见 [[ods-extraction-design]] 已知局限）。
- **Spec 3**：`docs/superpowers/specs/<date>-tech-relation-enrich-inference-design.md` — enrich worker LLM 推断。扩 `shared/enrich/orm_enricher`：对 tech profile 用 LLM 推演进/前置边 → `upsert_relation` + `EntityChangeLog(llm_enrich)`。

## 12. 部署/验收

- 重建：`docker compose -f deploy/docker-compose.yml up -d --build backend backend-worker frontend`。
- 重灌数据（含 EVOLVE/PREREQ 边）：`docker compose -f deploy/docker-compose.yml run --rm seed`。
- 清 E2E 污染：`psql ... DELETE FROM *_profile WHERE *_id LIKE 'E2E_IMPORT%'`。
- 验收：人工点「关系探索」两模式（含技术关系双视角）+ 技术详情「技术关系」Tab + drawer 节点跨画像跳转 + 面包屑回源。
