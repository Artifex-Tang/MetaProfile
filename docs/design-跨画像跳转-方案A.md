# 技术设计文档：关系图谱跨画像跳转（方案 A）

| 项 | 内容 |
|---|---|
| 模块 | MetaProfile 产业技术情报系统 · 四画像（人员/机构/项目/技术） |
| 主题 | 关系图谱节点点击 → 跨画像类型跳转 |
| 方案 | 方案 A（路由跳转 + 跳转上下文） |
| 状态 | 草稿 · 关键决策已定（路由模型=详情路由；无数据分级） |
| 关联文件 | `frontend/src/components/RelationGraph.tsx`、`frontend/src/pages/Profile*/index.tsx`、`frontend/src/App.tsx`、`metaprofile/shared/db/neo4j.py`、`metaprofile/profile_*/api/routes_relation.py` |

> 说明：关键决策已定（路由=详情路由；无数据分级；上下文含 evidence）。Reader Test 两轮通过（16/16 gap 修复，无新矛盾）。

---

## 1. 背景与目标

### 1.1 背景

系统已建成四类实体画像（技术 TECH、项目 PROJECT、机构 ORG、人员 PERSON）。每类画像详情中以关系图谱（`@antv/g6` 力导向图）展示当前实体与相邻实体的关联，节点按 `target_entity_type` 着色。

当前关系图谱仅作可视化与高亮（`activate-relations`），**点击节点无任何导航行为**。用户在查看某人员画像时，若需进一步查看其关联机构/项目/合作人员的画像，只能手动返回列表、检索、再打开，跨画像分析链路断裂。

### 1.2 目标

- 在任意画像的关系图谱中点击相邻节点，**跳转到该实体对应类型的画像视图**（人员↔机构↔项目↔技术，跨类型）。
- 跳转保留来源上下文：来源实体、关系类型、关系置信度、关系证据，支持返回（刷新后返回能力退化为返回来源实体，见 §4.2/§8）。
- 复用现有后端能力，不新增图谱查询接口。

### 1.3 非目标（明确排除）

- 图谱的编辑/关系创建 UX。
- 多跳路径的可视化展开（`find_path` 已具备能力，本方案不引入路径图，留作后续）。
- 关系数据本身的补全与纠错。
- 图谱节点与画像数据不一致的治理（单列异常处理，不改数据）。

---

## 2. 现状分析

### 2.1 已具备能力

| 能力 | 位置 | 说明 |
|---|---|---|
| 关系列表查询 | `GET /api/v1/relation/{person\|org\|project\|tech}/{id}` | 返回 `RelationList`，每项含跨类型目标 |
| 关系数据结构 | `RelationItem`（`api/types.ts`） | `relation_type` / `target_entity_id` / `target_entity_type` / `target_name` / `confidence` / `evidence` |
| 最短路径查询 | `POST /relation/{type}/path`、`Neo4jRepo.find_path` | `RelationPathRequest(from_id,to_id,max_depth≤6)` |
| 邻居查询 | `Neo4jRepo.get_neighbors` | 按 `label` + `rel_types` + `depth` 取邻居 |
| 图谱渲染 | `RelationGraph.tsx`（G6 force） | 中心 `_self` + 邻居节点（按类型着色）+ 边（按关系标注） |
| 图谱复用 | 四个 `Profile*` 页面 | 均在详情 Drawer 的 Tab 中渲染 `RelationGraph` |

### 2.2 缺口

1. `RelationGraph` 无 `onNodeClick` 导航回调；G6 `modes.default` 仅 `['drag-canvas','zoom-canvas','drag-node','activate-relations']`。
2. 节点模型未写入 `entityType`，tooltip 读取 `model.entityType` 恒为空，类型回退为"其它"（既有缺陷，本方案顺带修复）。
3. 路由无实体详情路由：`App.tsx` 仅 `/person` `/org` `/project` `/tech` 列表页，无 `/:id`。详情由页面内 `selectedId` 局部状态 + Drawer 承载。
4. 无跳转上下文（来源、关系、返回）承载机制。

---

## 3. 方案选型

### 3.1 候选方案对比

| 方案 | 做法 | 优点 | 缺点 | 结论 |
|---|---|---|---|---|
| **A（本方案）** | 点击节点 → 路由跳转到目标类型画像视图，携带跳转上下文（面包屑+返回） | 真正"跨画像"导航；可深链/分享；与详情视图一致；分析链路连贯 | 需引入实体详情路由或 focus 参数 | **采用** |
| B | 点击节点 → 弹出跨类型只读预览 Drawer（不离开当前页） | 改动小；不破坏列表状态 | 非"跳转"；无法递进深挖；预览信息受限 | 不采用 |
| C | 独立 `/graph/:type/:id` 全屏图谱探索页 | 探索能力强；路径展开空间大 | 偏离"画像"主线；工作量大；与既有 Drawer 详情割裂 | 留作后续 |

### 3.2 方案 A 定义

> **方案 A = 以"关系图谱节点"为入口的跨画像类型路由跳转。**
>
> 点击 `RelationGraph` 中任一邻居节点，系统读取该节点的 `target_entity_type` 与 `target_entity_id`，路由至对应类型画像视图并定位到该实体，同时携带来源上下文（来源实体类型/ID/名称、关系类型、置信度），在目标视图以面包屑形式呈现，并提供"返回来源"。

---

## 4. 总体设计

### 4.1 路由模型（已定）

采用新增实体详情路由：

```
/person/:id      /org/:id      /project/:id      /tech/:id
```

列表页 `/person` 等保持不变；新增详情路由复用现有 `Profile*` 组件，详情改为路由参数驱动（`useParams` 取 `id`），Drawer 仍用于列表内就地查看。

- 优点：深链可分享、可收藏；语义清晰；与后端 REST 一致；"跳转感"强，契合方案 A。
- 代价：四个页面需支持"路由 id 模式"（有 `:id` 时直接进入详情态）。

### 4.2 跳转上下文承载

跳转上下文最小集：

| 字段 | 来源 | 用途 |
|---|---|---|
| `fromType` | 当前画像类型（小写，见下注） | 面包屑、返回路由 |
| `fromId` | 当前实体 id | 返回定位 |
| `fromName` | 当前实体名称 | 面包屑展示 |
| `relationType` | 所点边/节点 `relation_type` | 面包屑"经 XX 关系" |
| `confidence` | `RelationItem.confidence` | 辅助展示（边虚化判定） |
| `evidence` | `RelationItem.evidence` | 关系证据原文，目标 404 时用于说明"为何存在此关系" |

> 类型大小写：后端 `EntityType` 为大写枚举（`TECH/PROJECT/ORG/PERSON`），故 `target_entity_type` 原值为大写；前端统一 `.toLowerCase()` 归一化为小写后再用于 `NAV_TYPE` 判定与路由（`/org/...`）。

承载方式（路由 state 为主，query 兜底）：

- 主：`navigate(\`/${type}/${id}\`, { state: { fromType, fromId, fromName, relationType, confidence, evidence } })`（React Router v6 `navigate` 的 `state` 入参）。state 不进 URL，刷新即丢失——此为本方案预期行为，刷新后视为直达（详情正常加载，仅面包屑退化，见 §8）。
- 兜底：同时写 `?from=${fromType}:${fromId}`（id 形如 `ORG_20260427_a1b2c3d4`，不含冒号，分隔安全；实现时仍对 `fromId` 做 `encodeURIComponent`）。刷新后据此还原来源类型与 id，可返回来源实体，但不还原关系类型/置信度/证据。

### 4.3 数据流

```
用户在 /person/:a 详情，查看关系图谱
  └─ RelationGraph 渲染 RelationList.items（来自 personService.getRelations(a)）
      └─ 点击邻居节点 X（target_entity_type=ORG, target_entity_id=b）
          └─ onNodeClick(X) → resolve(type=org, id=b, relation=ORG_PARENT, ...)
              └─ navigate('/org/b', {state:{fromType:person, fromId:a, fromName, relationType, confidence}})
                  └─ ProfileOrg 路由模式：useParams id=b → orgService.getById(b)
                      └─ 顶部面包屑：「人员 A —[隶属]→ 机构 B」+ [返回人员 A]
                          └─ 用户可继续在机构 B 图谱跳转，形成链式跨画像分析
```

复用现有接口：`getById`（详情）、`getRelations`（图谱）。**后端零新增。**

---

## 5. 详细设计

### 5.1 `RelationGraph`：节点点击 + 模型修复

文件：`frontend/src/components/RelationGraph.tsx`（依赖 `@antv/g6@4.8.x`，下述 API 均为 v4 写法）

1. 新增可选回调与可跳类型集合：
   ```ts
   export default function RelationGraph({
     relations, selfLabel, selfColor, height,
     onNodeClick,        // 新增：节点点击回调
     navTypes,           // 新增：可跳类型集合（小写），决定哪些节点响应点击/hover
   }: {
     relations: RelItem[]
     selfLabel?: string
     selfColor?: string
     height?: number
     onNodeClick?: (item: { id: string; type?: string | null; name?: string | null; relationType?: string | null; confidence?: number | null }) => void
     navTypes?: Set<string>
   })
   ```
2. 节点模型写入 `entityType`（修复 tooltip）：
   ```ts
   const nodes = relations.map(r => {
     const m = metaOf(r.target_entity_type)
     return {
       id: r.target_entity_id,
       entityType: r.target_entity_type,   // 新增：tooltip 正确显示类型
       relationType: r.relation_type,      // 新增：点击时回带关系
       confidence: r.confidence,
       name: r.target_name,
       label: r.target_name ?? r.target_entity_id.slice(0, 8),
       /* …既有样式… */
     }
   })
   ```
3. 注册点击行为（二选一，均仅对 `navTypes` 命中节点触发）：
   - 方式一（轻量，推荐）：`graph.on('node:click', e => { const m = e.item.getModel(); if (!navTypes?.has(String(m.entityType).toLowerCase())) return; onNodeClick?.({ id: m.id, type: m.entityType, name: m.name, relationType: m.relationType, confidence: m.confidence }) })`。需配合拖拽阈值校验，避免拖拽误触发跳转（见 §11）。
   - 方式二：在 `modes.default` 增加 `click` 行为。避免新增交互模式与 `drag-node` 冲突，故不优先。
4. 视觉与可跳判定：hover 高亮与 `cursor: pointer` **仅作用于可跳节点**（`navTypes` 命中者）。可跳判定数据来源：组件 prop `navTypes`（页面层传入，默认即四类画像）。未命中者保持普通指针，避免"看起来可点却无响应"。

### 5.2 页面层：跳转编排

各 `Profile*` 页面引入 `useNavigate`（`react-router-dom` v6）。**以下以 `ProfilePerson` 为例**，其余三类（Org/Project/Tech）替换类型字面量与名称字段（如 `fromType:'org'`、`o?.name_cn`）。

```ts
const navigate = useNavigate()
const handleNodeClick = (n) => {
  const type = (n.type ?? '').toLowerCase()       // 后端为大写 EntityType，归一化为小写
  if (!NAV_TYPE.has(type)) return                 // 仅四类画像可跳
  navigate(`/${type}/${n.id}`, {
    state: { fromType: 'person', fromId: id, fromName: p?.name_cn,
             relationType: n.relationType, confidence: n.confidence, evidence: n.evidence },
  })
}
// 渲染（navTypes 透传，控制哪些节点可点/hover）：
<RelationGraph relations={relations.data.items} selfLabel="当前人员"
               onNodeClick={handleNodeClick} navTypes={NAV_TYPE} />
```

`NAV_TYPE`：`{'tech','project','org','person'}`（小写）；`enterprise`/`strategy` 等暂不跳转（见 §8）。

### 5.3 路由与详情定位

`App.tsx` 新增（路由模型见 §4.1）：

```tsx
<Route path="person/:id" element={<ProfilePerson />} />
<Route path="org/:id" element={<ProfileOrg />} />
<Route path="project/:id" element={<ProfileProject />} />
<Route path="tech/:id" element={<ProfileTech />} />
```

各 `Profile*` 组件：`const { id: routeId } = useParams()`；存在 `routeId` 时初始化 `selectedId = routeId` 并打开 Drawer（或直接进入详情视图）。无 `routeId` 时维持现有列表行为。

### 5.4 跳转上下文面包屑

`Profile*` 顶部（或 Drawer 标题区）读取 `useLocation().state`。**返回入口与面包屑合二为一**——面包屑的"来源实体"项即返回入口，不另设独立按钮：

```tsx
const loc = useLocation()
const ctx = loc.state as JumpCtx | null
ctx && <Breadcrumb>
  <Breadcrumb.Item>
    <a onClick={() => navigate(`/${ctx.fromType}/${ctx.fromId}`)}>{ctx.fromName ?? ctx.fromId}</a>
  </Breadcrumb.Item>
  <Breadcrumb.Item>经「{REL_LABEL[ctx.relationType] ?? ctx.relationType}」</Breadcrumb.Item>
  <Breadcrumb.Item>{当前实体名}</Breadcrumb.Item>
</Breadcrumb>
```

- `REL_LABEL`：复用 `RelationGraph.tsx` 既有映射（英文关系枚举/中文值 → 中文展示）；未覆盖键回退原值。
- 返回实现：**统一用显式 `navigate(\`/${ctx.fromType}/${ctx.fromId}\`)`**（不依赖历史栈，链路清晰）。`navigate(-1)` 不采用——历史栈可能被链式跳转/外部页污染。
- 刷新后 `state` 丢失：仅能由 `?from=` 还原来源类型与 id，面包屑退化为"来源实体（无关系标注）"；详情本身正常。

### 5.5 后端

**无需新增接口。** 复用 `GET /api/v1/relation/{type}/{id}`、`GET /api/v1/profile/{type}/{id}`。`Neo4jRepo.get_neighbors`/`find_path` 暂不调用（图谱仅取一跳邻居，已由 relation 接口满足）。

现有 `getRelations` 返回的 `target_entity_type` 主体取值为 `tech/project/org/person`（与 `EntityType` 一致）。`enterprise`/`strategy` 为扩展类型，无对应画像页，不参与跳转。

> **类型占比估算（业界类比，待生产数据校准）：** 工业技术情报/专利图谱类系统中，关系端点以机构（org）与人员（person）为主（合计约 55–70%），技术（tech）约 15–20%，项目（project）约 10–15%；企业（enterprise）多与机构重叠、战略（strategy）为稀疏长尾，二者合计约 5–10%。故将 `enterprise/strategy` 暂列不可跳类型对整体可用性影响有限；上线后按实际统计复核，若合计 >15% 则启动扩展类型画像页评估。

---

## 6. 交互与视觉

| 元素 | 规范 |
|---|---|
| 可跳转节点 | `cursor: pointer`；hover 描边加粗（`lineWidth: 3`，`stroke: #1677ff`） |
| 中心 `_self` 节点 | 不响应跳转（点击无动作或提示"当前实体"） |
| 不可跳转类型节点 | 普通指针；tooltip 提示"该类型暂不支持跳转" |
| 面包屑 | 顶部，灰底；来源实体可点击返回 |
| 关系标注 | 沿用 `REL_LABEL`（复用 `RelationGraph.tsx`）；置信度 < 0.5 时边虚化（`lineDash`），阈值取既有渲染惯例，可配置 |
| 加载态 | 跳转后目标详情 `useQuery` 期间显示 `Spin`，保持图谱骨架 |

---

## 7. 时序（典型链式跳转）

```
Person A 详情
  → 点击邻居 Org B（ORG_PARENT）
    → /org/B  (state: from=person:A, rel=ORG_PARENT)
      → ProfileOrg 加载 Org B 详情 + 其关系图谱
        → 点击邻居 Project C（ORG_UNDERTAKE_PROJECT）
          → /project/C (state: from=org:B, rel=ORG_UNDERTAKE_PROJECT)
            → … 链式跨画像分析，任意点可"返回来源"
```

每次跳转均为一次 `getById` + `getRelations`，与现有列表打开 Drawer 成本相当。

---

## 8. 边界与异常

| 场景 | 处理 |
|---|---|
| `target_entity_type` 为 `enterprise`/`strategy`/未知 | 不跳转；tooltip 提示；记录日志便于后续扩展评估 |
| `target_entity_id` 在目标类型中不存在（关系悬空） | 目标 `getById` 404；展示"该实体画像不存在（关系数据可能过期）"+ 返回来源 + 保留关系证据 `evidence` |
| 点击中心 `_self` | 无动作 |
| 关系 `confidence` 缺失 | 默认 0.7（沿用 `RelationGraph` 既有渲染默认值） |
| 刷新详情页 | `state` 丢失，面包屑退化为仅 `?from=` 还原的来源类型（不还原关系）；详情本身正常加载 |
| 他人通过分享链接打开（带 `?from=`，无 `state`） | 行为同刷新：正常进入详情，面包屑仅还原来源类型；无 `?from=` 时不显示面包屑 |
| 深链直达 `/:type/:id`（无 `?from=`） | 无上下文，正常进入详情，不显示面包屑 |
| 自环（跳转目标 = 来源） | 不跳转 |

---

## 9. 改动清单

| 文件 | 改动 | 类型 |
|---|---|---|
| `frontend/src/components/RelationGraph.tsx` | 增加 `onNodeClick`+`navTypes`；节点模型补 `entityType/relationType/name`；注册 `node:click`（仅可跳节点）+ hover；cursor | 修改 |
| `frontend/src/App.tsx` | 新增 4 条 `/:type/:id` 详情路由（见 §4.1） | 修改 |
| `frontend/src/pages/ProfilePerson/index.tsx` | `useNavigate`+`handleNodeClick`；路由 id 模式（`useParams`）；面包屑；`onNodeClick`+`navTypes` 透传 | 修改 |
| `frontend/src/pages/ProfileOrg/index.tsx` | 同上（类型字面量替换为 org） | 修改 |
| `frontend/src/pages/ProfileProject/index.tsx` | 同上（类型字面量替换为 project） | 修改 |
| `frontend/src/pages/ProfileTech/index.tsx` | 同上（类型字面量替换为 tech） | 修改 |
| `frontend/src/api/types.ts`（可选） | 增加 `JumpCtx` 类型；`RelItem` 已与 `RelationItem` 字段对齐，无需改动 | 修改 |
| 后端 | 无 | — |

预计工作量（前端）：约 1–1.5 人日。拆解：`RelationGraph` 改造 ~0.3d；四个 `Profile*` 页面路由 id 模式 + 跳转 + 面包屑 ~0.6d（每页 ~0.15d，模式一致）；`App.tsx` 路由 + 联调自测 ~0.4d。

---

## 10. 测试要点

- 单元：`RelationGraph` `onNodeClick` 回调携带正确 `{id,type,name,relationType,confidence}`；中心节点不触发。
- 路由：`/person/:id` 进入即定位该实体；无 id 维持列表；深链可直达。
- 跳转：四种类型有向跳转矩阵共 12 条（4×3，A→B 与 B→A 各计，不含自环），均正确路由 + 面包屑正确。
- 上下文：`state` 携带字段完整（含 `evidence`）；面包屑"来源实体"点击返回定位准确。
- 异常：悬空目标 404 提示；未知类型不跳转；刷新后退化为 `?from=`；分享链接（带 `?from=`、无 `state`）行为同刷新。
- 回归：既有列表双击/详情按钮、Drawer 行为不受影响。

---

## 11. 风险与未决

| 项 | 说明 | 处置 |
|---|---|---|
| `target_entity_type` 实际取值分布 | 决定可跳转类型集合 | 上线后按生产统计复核（见 §5.5 估算） |
| `state` 刷新丢失 | 面包屑降级为仅来源类型（不还原关系） | `?from=` 兜底，属预期行为；若产品要求刷新后仍显示关系，则需将关系信息一并写入 query |
| G6 4.x `node:click` 与 `drag-node` 事件区分 | 拖拽误触发跳转 | 实现时校验 `e.item` 与拖拽阈值，必要时改用 `click` 事件 |
| 版本前提 | 已确认 `react-router-dom@6.22`、`@antv/g6@4.8`，文中 API（v6 `navigate(state)`、v4 `node:click`/`getModel()`）均匹配 | 无 |

---

## 12. 后续演进（非本期）

- 全屏图谱探索页（方案 C）：接入 `find_path`/`get_neighbors` 多跳展开。
- 跨类型全局搜索式跳转入口（命令面板）。
- 跳转路径历史栈可视化（分析足迹）。
- 关系悬空实体的批量治理与补建。
