# 技术概念抽取与 tech-tech 关系挖掘 设计

**日期**: 2026-06-21
**状态**: P1 已完成合 main(`beff234`, 2026-06-24)——IPC L1 骨架 + LLM L2 聚类 + TECH_CONTAINS 树 + 证据 + name_cn 英文归一均落地。#3 禁 patent-as-tech(降为 evidence)亦并入。P2 共现网 / P3 演进链待独立计划。
**背景**: 冷启动里程碑。metadata 1:1 模式跑通真 ODS 数据后暴露:Tech 画像把论文/专利**标题当技术名**(100 个假技术),且 **ingest_ods 零 tech-tech 挖掘**。本设计落地"技术概念抽取层",产出技术树/网/链 + 把论文/专利降为证据。

---

## 1. 问题与目标

### 1.1 现状缺陷
- `ods_science_literature.title` / `ods_invention_patent_cn.title` → `tech_name`,**1 文档 = 1 技术**,造出"假技术"(论文标题 ≠ 技术名)。
- 多篇论文/专利讲同一技术(质谱仪)→ 被当成多个不同技术,无法聚合。
- 零 tech-tech 关系(关系图谱里只有 人-技术 / 机构-技术)。

### 1.2 目标
1. **抽取真技术实体**:从文档(标题/摘要/权利要求/全文)抽技术概念,跨文档聚类去重。
2. **IPC 骨架**:用 IPC subclass 做确定性技术域(L1),覆盖有 ipc_type 的专利。
3. **tech-tech 三种结构**:
   - **树**:IPC 层级(section→subclass)→ 具体技术(L2)包含关系。
   - **网**:共文档/共发明人/共 IPC/语义相似 共现边。
   - **链**:problem-solution 演进(LLM,同域 filing_date 时序)+ IPC 共类时序。
4. **论文/专利降为证据**:1 文档 = 1 条证据,挂到技术下,非技术本身。

### 1.3 非目标(本次不做)
- **引文依赖链**:ODS 无引文数据(raw_content 空、clean 无可抽专利号引用)。引文链留待外部源(Google Patents/EPO/Lens)接入,本设计仅标注为数据缺口。
- 跨语言大规模聚类优化(先用 embedding 阈值 + 词典,不追求 SOTA)。
- 前端技术树/链可视化(后端产出关系即可,前端另议)。

---

## 2. 实体模型

### 2.1 Tech 两层

| 层 | 来源 | tech_id 格式 | tech_name | 覆盖 |
|---|---|---|---|---|
| **L1 IPC 技术域** | 专利 IPC subclass(A01C/G06T) | `ipc:G06T` | IPC subclass 中文名(IPC 字典) | 有 ipc_type 的专利(~35%) |
| **L2 具体技术** | LLM 抽术语 + 聚类 | `concept:{slug}` 或 `concept:{md5(term)[:12]}` | 规范技术术语(质谱仪/量子计算) | 全部文档(含无 IPC + science) |

- **存储**:复用 `tech_profile` 表,新增列区分层(见 §4.1)。L1/L2 同表,`tech_layer` 字段区分。
- **L2→L1 归属**:Neo4j `TECH_CONTAINS` 边(L1 contains L2);L2 行冗余 `parent_ipc_code` 列便于 SQL 过滤。
- **L1 无 ipc_type 专利 / 全部 science**:不产 L1,其 L2 技术若找不到归属 IPC,`parent_ipc_code` 留空(孤立 L2,待后续归类)。

### 2.2 证据(论文/专利)
- 论文/专利**不再建为 tech 实体**。
- 一篇文档 = 一条证据,记录"该文档提及哪些 L2 技术"。
- 存储:新表 `tech_evidence`(见 §4.2),`(tech_id, source_doc_id, source_table, snippet)`。
- 通过 `tech_evidence` 可查"某技术被哪些论文/专利支撑"。

---

## 3. tech-tech 关系(三种结构)

### 3.1 树(确定性,IPC 层级)
- 边:`IPC_SECTION —CONTAINS→ IPC_SUBCLASS(L1) —CONTAINS→ L2 具体技术`。
- 来源:IPC 字典层级 + 文档 IPC subclass。
- 是否建 section 节点:建(8 个 section 节点 + subclass L1 + L2),构成 ≤3 层树。section/subclass 节点不入 `tech_profile`,只在 Neo4j 作层级节点(或 L1 的 parent 指向 section 节点)。

### 3.2 网(共现)
边 `TECH_CO_OCCURS` 产生条件(L2 之间):
- **同文档**:同一篇论文/专利被 LLM 抽出 ≥2 个 L2 技术 → 两两共现。
- **同发明人**:同 inventor 的不同文档抽出的 L2 技术(跨文档)。
- **共 IPC**:同 subclass 下聚出的 L2 技术(隐含同域,转共现边)。
- **语义相似**:两 L2 技术名 embedding cosine ≥ 阈值(默认 0.88,可配)。
- 每条边带 `confidence`(共现次数归一 / cosine 值)+ `evidence`(来源文档)。

### 3.3 链(演进,降级)
边 `TECH_EVOLVES_FROM`:
- **problem-solution 演进**:LLM 从专利 claims/说明书抽 `(problem, solution, improvement)` 三元。同 IPC subclass 域内,按 `filing_date` 时序,前驱技术 → 后继技术(解决相似 problem / 改进前驱)。
- **IPC 共类时序兜底**:无 problem-solution 时,同 subclass 按 filing_date 排,相邻专利的技术 → 弱演进边(confidence 低)。
- **引文链缺**:数据阻断,标注 TODO(外部源)。

---

## 4. 数据模型变更

### 4.1 `tech_profile` 新增列
```
tech_layer      VARCHAR(16) NOT NULL DEFAULT 'CONCEPT'  -- DOMAIN | CONCEPT
ipc_code        VARCHAR(32) NULL                        -- L1: subclass code (G06T)
parent_ipc_code VARCHAR(32) NULL                        -- L2: 归属 subclass
cluster_terms   JSON         DEFAULT []                 -- L2: 同义合并的原始术语集
```
- 迁移:alembic 新 revision 加 4 列。
- 现有 100 标题-tech:**删除**(它们是无 layer 的错误实体),重跑产出两层。

### 4.2 新表 `tech_evidence`
```
tech_evidence (
  id            BIGSERIAL PK,
  tech_id       VARCHAR(64) NOT NULL,    -- L2 (或 L1)
  source_doc_id VARCHAR(128) NOT NULL,   -- 论文/专利 original_id
  source_table  VARCHAR(128) NOT NULL,   -- ods_science_literature / ods_invention_patent_cn
  snippet       TEXT,                    -- 抽取命中文本片段(≤500 字符)
  confidence    FLOAT DEFAULT 0.0,
  created_at    TIMESTAMPTZ DEFAULT now(),
  UNIQUE(tech_id, source_doc_id, source_table)
)
```

### 4.3 新 RelationType(枚举 + _PREDICATE_MAP)
- `TECH_CONTAINS` —— L1 contains L2 / section contains subclass。
- `TECH_CO_OCCURS` —— L2 共现。
- `TECH_EVOLVES_FROM` —— 演进链。
加到 `RelationType` 枚举 + `ingest_ods/llm/prompts._PREDICATE_MAP`(若 LLM 抽出)。

### 4.4 IPC 字典(`ipc_taxonomy`)
- 数据:`metaprofile/ingest_ods/data/ipc_subclass_cn.tsv`(subclass\中文名),覆盖 WIPO ~600 subclass。
- 来源:本次先手工/脚本生成 top 高频 subclass(从已同步专利 `ipc_type` 聚合 top-N),补全留 follow-up。字典缺失时 `tech_name` fallback = subclass code 原文(如 `G06T`)。
- 模块:`domain/ipc_taxonomy.py`:函数 `subclass_of(ipc_type)`(回卷到 subclass)、`name_of(subclass)`、`section_of(subclass)`。

---

## 5. 流水线(ingest_ods 扩展)

复用现有 5 阶段,在 `extract`(表→表)后、`write` 前插入 **tech-concept 阶段**:

```
extract(表→staging) → [新] tech_concept_mine(技术概念+聚类) → resolve/merge → score → write(profile + Neo4j tech-tech)
```

### 5.1 阶段输入/输出
- 输入:patent/science 行(title/abstract/claims/clean_content + ipc_type + inventor + filing_date)。
- 输出:
  - L1 tech(IPC subclass)+ L2 tech(聚类后概念),写入 `tech_profile`。
  - `tech_evidence` 行。
  - tech-tech 三类边 → Neo4j。

### 5.2 LLM 调用(选择性,两阶段原则延续)
- **L1 零 LLM**:subclass 回卷 + 字典查名,纯规则。
- **L2 用 LLM**:从 title/abstract/claims 抽技术术语(structured output)。
- **problem-solution 用 LLM**:抽 (problem,solution,improvement)。
- 共现/语义边零 LLM(集合运算 + embedding 余弦)。
- 模型:复用 `settings.llm.extraction_model`(glm-4.7),走 `LLMGateway`。

---

## 6. 组件(ingest_ods 新模块)

| 模块 | 职责 |
|---|---|
| `domain/ipc_taxonomy.py` | IPC 回卷 + 字典查名 + 层级(section/subclass) |
| `services/tech_concept_miner.py` | LLM 从文档抽技术术语(MinedTechTerm) |
| `services/tech_clusterer.py` | 同义聚类(词典归一 + embedding cosine ≥ 0.92)→ L2 entity_id |
| `services/tech_relation_builder.py` | 建 TECH_CONTAINS / TECH_CO_OCCURS / TECH_EVOLVES_FROM 边 |
| `services/problem_solution_miner.py` | LLM 抽 (problem,solution,improvement),产出演进链 |
| `domain/orm_models.py` 扩展 | TechEvidenceORM + tech_profile 新列 |
| `migrations/000X_tech_concept.py` | alembic:加列 + tech_evidence 表 |

---

## 7. 聚类与同义合并(关键技术风险)

- **归一**:lowercase + 去标点 + 别名词典(`质谱仪`=`质谱`=`mass spectrometry`=`MS`)。词典初版手工 top-N 高频术语,可扩。
- **embedding 合并**:bge-large-zh embedding,cosine ≥ `WEAK_SIGNAL`/新阈值(默认 0.92)→ 合并到同一 L2 entity。
- **entity_id 稳定**:`concept:{md5(normalized_term)[:12]}`,保证跨批幂等。
- **不完美可接受**:本阶段目标是"聚合掉明显同义",不追求零误差;误合/漏合留 follow-up 调阈值/词典。

---

## 8. 测试策略(TDD)
- `test_ipc_taxonomy`:回卷(G06T7/00(2017.01)I → G06T)+ section/subclass 层级 + 字典查名(含 fallback)。
- `test_tech_concept_miner`:mock LLM → 抽术语结构化校验。
- `test_tech_clusterer`:同义合并(质谱仪/质谱/MS → 1 entity)+ 不合并无关 + entity_id 幂等。
- `test_tech_relation_builder`:三类边构造 + confidence/evidence 附带。
- `test_problem_solution_miner`:mock LLM → 演进链按时序。
- 端到端:小批 patent+science → 产出 L1+L2+边+evidence,断言 tech-tech 边存在。

---

## 9. 风险与缓解
| 风险 | 缓解 |
|---|---|
| 聚类同义合并不准 | 词典 + embedding 阈值,可调;不追求完美 |
| IPC 中文名字典不全 | fallback = subclass code;top-N 先行,补全 follow-up |
| problem-solution 抽取质量依赖 claims 全文 | clean_content 已有(pubscholar 5K);prompt 调优 + 抽样人工抽检 |
| 65% 无 ipc_type 专利无 L1 | L2 仍可产(孤立,`parent_ipc_code` 空);后续按 embedding 归类 |
| LLM 成本 | 两阶段延续:规则优先,L1/共现/语义零 LLM;仅 L2 抽取 + problem-solution 用 LLM |

---

## 10. 分期交付(建议)
- **P1(先落地看效果)**:L1 IPC 骨架 + L2 LLM 抽取 + 聚类 + TECH_CONTAINS 树 + 证据表。技术树 + 具体技术 + 证据溯源可见。
- **P2**:共现网(TECH_CO_OCCURS)+ 语义相似边。技术网可见。
- **P3**:problem-solution 演进链(TECH_EVOLVES_FROM)。技术链(降级)可见。
- 引文链:外部源接入后单独迭代。

---

## 11. 开放问题(spec 写定时默认,review 可调)
- section 节点是否入 Neo4j(默认:入,8 个,作树根)。
- L2 孤立(无 IPC)是否尝试 embedding 归到最近 L1(默认:P2 再做)。
- 证据 snippet 截断长度(默认 500 字符)。
- embedding 阈值(聚类 0.92 / 共现语义 0.88,均可配)。

---

**下一步**:用户 review 本 spec → 通过后 invoke `writing-plans` 出实施计划(按 P1→P2→P3 拆 TDD 任务)。
