# 科技情报挖掘升级设计:新技术发现 / 弱信号 / 颠覆性识别 / 实体挖掘

- 日期:2026-10-14
- 状态:设计定稿;**Phase A 已实现含审查修复+M1 真数据验证通过**(2026-10-14 本地 Doris `G:/docker/doris` 19G 全在,库 `ods_zbzx`;8 源真语料 89,971 候选→122 信号+155 真共现边+1,144 term_stats 行落库;重扫幂等验证 122/155/1144 不变;attachment 表探测优雅跳过实证)。真跑补修:IN 参数>32767 分块(候选百万级)+`max_signals=500` 护栏(首轮阈值地板防边爆炸)
- 审查遗留 follow-up:L11(掉出信号的旧边不清理)/L14(ORM 无 server_default 的 schema 漂移+spec BIGSERIAL vs INT)/L16(domain→industry 逐字匹配,无归一;未来 attachment 表须含 industry 列)/related_*_ids 本地仅 mock 画像故空(Phase D ROR 后实化)
- 输入:全网方法学调研(2026-10-14)、开源调研(2026-10-14)、现有代码盘点
- 前置:弱信号子项目1(`2026-06-20-weak-signal-pipeline-design.md`)、技术概念 P1(`2026-06-21-tech-concept-extraction-design.md`)

### 实施状态速查(2026-10-14)
| 任务 | 状态 | 落点 |
|---|---|---|
| A1 修语料 bug(G1-G3) | ✅ | `corpus_loader.py`(SourceSpec+optional 探测) |
| A2 扩 4 源+industry 过滤 | ✅ | 同上;extractor `domain→industry` |
| A3 term_stats 表+计数 | ✅ | `TermStatORM`+migration `0010`+`evidence_builder.persist_term_stats`;`signal_metrics.build_term_stats` df/tf 计数化(修 G8) |
| A4 证据回填 | ✅ | `entity_linker.py`+`weak_signal_extractor._link_evidence` |
| A5 真共现边 | ✅ | `evidence_builder.cooccurrence_pairs`+`_write_cooccurrence_edges`(先删旧 co_occurrence 边防重复) |
| A6 DDL 对齐测试 | ✅ | `tests/new_tech/test_corpus_loader_sources.py`(解析 `_doris_local_schema.sql` 校验列名) |

---

## 1. 目标与范围

四问:
1. **挖掘新技术**(新兴技术识别)
2. **发现弱信号**(多源早期信号)
3. **发现颠覆性新技术**(disruptive tech)
4. **挖掘人/机构/项目/技术**(实体挖掘增强)

硬约束:
- **全库无引文数据**(ODS patent/science 均无 citation 字段)→ CD index、引文网络、co-citation 原生不可算,全部用 citation-free 替代。
- LLM 配额有限(glm 429 教训)→ **统计层跑全库零 LLM;LLM 只碰漏斗末端 Top-N**。
- GPL 库(pybibx/cdindex)不 import 进主代码;Kleinberg burst ~100 行自研(MIT 参考 fastbursts)。
- 云上 readonly 栈无 Doris/ES/worker → 全部能力落在本地全栈,云上按需裁剪。

## 2. 方法学结论(调研摘要)

### 2.1 采纳(按 落地顺序)

| # | 方法 | 出处 | 输入需求 | 落点 |
|---|---|---|---|---|
| 1 | **Porter 新兴指标**:活跃实体数、新进入者占比、倍增时间 DT=ln2/ln(1+g)、参与广度 | Porter et al. / Small;JRC 弱信号报告同款 | year+applicant/inventor | L1 指标层(每 IPC 域/每 L2 概念) |
| 2 | **TLC/Haupt**:专利数增速 vs 申请人增速比 + Gompertz S 曲线阶段 | Haupt 2007;EPO 2023 | filing_date+applicant | L1 指标层 |
| 3 | **TEM 象限**:主题份额(低)×增速(高)=弱信号;切点 x=均值,y=0 | WISDOM arXiv:2409.15340 | count | L1 指标层(L2 概念) |
| 4 | **IPC 共类融合**:新跨域 IPC 对(Salton/Jaccard 强度上升) | Curran & Leker 2011 | ipc_type+year | L1 指标层 + 融合信号 |
| 5 | **Wang 组合新颖性**(无引文改造):文档 IPC 对中"历史从未出现"对占比 | Wang/Veugelers/Stephan NBER w22180 | ipc_type 多值 | L2 颠覆分项 |
| 6 | **DisruptScore 加权**:0.3·跨域新颖 + 0.25·增速 + 0.2·新进入者 + 0.15·小团队(inventor≤3) + 0.1·术语新度 | 中文漏斗模型合成(陈伟 2024 等) | 上述指标组合 | L2 颠覆层 |
| 7 | **LLM rubric 评分**:Rotolo 五属性(novel/growth/impact/coherence/ambiguity)1-5 分×3 次中位,仅漏斗后 Top-N | Rotolo 2015;Ikoma 2025;Predictive Patentomics 2023 | 候选证据卡 | L2 颠覆层 |
| 8 | **ROR 机构归一**:ROR CC0 数据 + rapidfuzz 别名匹配 | ror.org | 机构名字符串 | L3 实体层 |
| 9 | **作者消歧**(轻量):blocking(姓+首字母)+ 共作者/机构/年份规则聚类 | OpenAlex/S2AND 思路,规则版 | authors+employer+year | L3 实体层 |
| 10 | **LLM 项目分类**:项目 name/desc → L1 IPC 域零样本分类 | LLM 零样本分类 | project 表 | L3 实体层 |
| 11 | **真共现网络**:同文档术语对/实体对频次边(替换现 REST 启发式边) | Small 共词聚类 | 语料 | L1/L2 |
| 12 | **Kleinberg burst 升级**(可选,后置):现有 z-score 够用,真 Kleinberg Viterbi 版列为增强 | Kleinberg 2002 | year+count | 增强 |

### 2.2 淘汰/后置

| 方法 | 原因 |
|---|---|
| CD index(Funk)/DISRED | 无引文;DISRED 查无此方法(记忆偏差) |
| 引文网络 TLC / co-citation / science linkage | 无引文 |
| Uzzi 引文对 z 分数 | 无引文(用 IPC 对替代,见 #5) |
| BERTopic 全库主题空间 | 后置(向量底座本地 GPU 未定,先 IPC+术语层);列为 P2 增强 |
| S2AND 预训练消歧 | 重(LightGBM+嵌入),先规则版 |
| agentic 科学家(FutureHouse 类) | ROI 低,后置 |

### 2.3 开源采纳

| 库 | 用途 | 许可 | 方式 |
|---|---|---|---|
| rapidfuzz | 机构/术语模糊匹配 | MIT | pip 直接用 |
| ROR data dump | 机构字典(名称/别名/层级) | CC0 | 数据文件 |
| splink(可选) | 大规模记录链接 | MIT | Phase D 视量级 |
| fastbursts(参考) | Kleinberg 参考实现 | MIT | 参考不 import |
| Neo4j GDS 插件(可选) | louvain/pagerank 社区 | 社区版可用 | Phase E 视需 |

## 3. 总体架构(五层)

```
L0 地基层(修复+扩源)
  Doris ODS 31表 → CorpusLoader 8源(science/patent/market/policy/events/report/news/+attachment*)
  → 预处理(jieba/停用词/术语典/月窗) → term_stats 持久化(窗口×术语×源 df/tf)
  → 证据关联:top docs→evidence_doc_ids,共现实体→related_*_ids,真共现边

L1 新兴指标层(零 LLM,全库)
  对象:IPC L1 域(636) + L2 概念(concept:*) + 新 IPC 对
  指标:Porter(活跃/新进入者/DT/广度) + TLC/Haupt(S曲线+增速比) + TEM 象限 + IPC共类融合强度
  存储:tech_emergence_indicator 表(对象×窗口×指标);TEM 象限分类标 weak/emerging/mature/declining

L2 颠覆识别层(统计+漏斗末端 LLM)
  分项:z(组合新颖 IPC新对比) + z(增速) + z(新进入者) + z(小团队占比) + z(术语新度)
  合成:DisruptScore = 0.30/0.25/0.20/0.15/0.10 加权(权重可配)
  漏斗:DisruptScore Top-N(默认200) → LLM Rotolo rubric(3次中位) → verdict+evidence
  存储:disruption_assessment 表;前端 NewTechDiscovery 新"颠覆性"Tab

L3 实体挖掘层
  ROR 归一(org 名→ROR ID+合并建议+ORG_SIBLING 边) + 作者消歧(规则聚类→person 合并) + 项目 LLM 分类(→tech_domain)

L4 情报管线串联(子项目2/3)
  弱信号+新兴指标+颠覆分 → frontier 候选 → 5维 fusion(现有 scorer 换真数据源) → LLM 验证(现有 validator)
  → validated frontier → topic_candidate(子项目3) → cron(weak_signal/frontier_scan 新任务类型)
```

数据流大图见 `docs/diagrams/tech-intel-mining-architecture.drawio`(5 页)。

## 4. 差距分析(现有 vs 目标)

### 4.1 🔴 阻断性 bug(Phase A 修)

| # | 问题 | 位置 | 影响 |
|---|---|---|---|
| G1 | science 源时间列 `pubdate` 不存在(实际 `event_time`) | `corpus_loader._SOURCE_SPECS` | science 5.58M 语料查询必失败→弱信号吃不到论文源 |
| G2 | patent 源实体列 `Inventor` 不存在(在 features JSON) | 同上 | patent 源查询失败→6M 专利语料丢失 |
| G3 | `attachment_text` 表不存在(附件 spec 未实现) | 同上 | 该源每次报错降级空(噪音) |

→ **真语料只有 market 一源能跑**。弱信号"真算法"实际从未在真多源语料上跑过。

### 4.2 断链/空心(Phase A/B 修)

| # | 问题 | 现状 | 目标 |
|---|---|---|---|
| G4 | `POST /frontier-tech/scan` 纯 demo | 从不调 `ScanMonitorService.run_scan` | 真跑 5-scorer fusion(子项目2) |
| G5 | `evidence_doc_ids`/`related_*_ids` 恒 `[]` | 提取器不产出 | 语料 top docs+共现实体回填 |
| G6 | 网络边=REST 启发式(同域 0.5 等) | NetworkCorrelator 调画像 REST | 真语料共现边 |
| G7 | 无时序存储 | 每次重算全窗口 | term_stats 持久化 |
| G8 | coherence 用 presence 常量 1 非计数 | T7 已知局限 | df 计数(随 G7 解决) |
| G9 | 31 表只用 4 张 | policy/events/report/news 闲置 | +4 源 |

### 4.3 缺失能力(Phase B/C/D/E 建)

| # | 能力 | 现状 |
|---|---|---|
| G10 | 新兴指标(Porter/TLC/TEM/IPC融合) | 零 |
| G11 | 颠覆性识别(组合新颖/DisruptScore/LLM rubric) | 零(全库无 disruption 概念) |
| G12 | ROR 机构归一 | 零(org 名靠 ingest 硬匹配) |
| G13 | 作者消歧 | 零 |
| G14 | 项目 LLM 分类 | 零 |
| G15 | tech-tech 真挖掘 P2(TECH_CO_OCCURS)/P3(TECH_EVOLVES_FROM) | 枚举在,无 builder |
| G16 | weak_signal/frontier cron 任务类型 | 调度器只有 translate/collection |
| G17 | 子项目3(前沿→选题) | 零 |

## 5. 数据模型变更

```sql
-- 0010 migration
term_stats (                       -- L0:窗口×术语×源计数(持久化,G7/G8)
  id BIGSERIAL PK,
  window_month DATE NOT NULL,      -- 月窗
  source VARCHAR(32) NOT NULL,     -- science/patent/market/policy/...
  term VARCHAR(255) NOT NULL,      -- 归一后术语/实体名
  term_kind VARCHAR(16) NOT NULL DEFAULT 'term',  -- term|entity
  df INT NOT NULL, tf INT NOT NULL,
  UNIQUE(window_month, source, term, term_kind)
)

tech_emergence_indicator (         -- L1:对象×窗口×指标
  id BIGSERIAL PK,
  object_type VARCHAR(16) NOT NULL,   -- ipc_domain|concept|ipc_pair
  object_id VARCHAR(128) NOT NULL,    -- ipc:G06T / concept:abc / G06T-G06N
  window_month DATE NOT NULL,
  metrics JSONB NOT NULL,             -- {active_entities,new_entrant_ratio,doubling_time,tem_share,tem_growth,tem_quadrant,s_curve_stage,haupt_ratio,...}
  UNIQUE(object_type, object_id, window_month)
)

disruption_assessment (            -- L2:颠覆评估
  id BIGSERIAL PK,
  object_type VARCHAR(16) NOT NULL,   -- concept|ipc_pair
  object_id VARCHAR(128) NOT NULL,
  window_month DATE NOT NULL,
  novelty_comb ZREAL, growth_score REAL, new_entrant_score REAL, small_team_score REAL, term_novelty_score REAL,
  disrupt_score REAL NOT NULL,
  llm_verdict VARCHAR(16),            -- pending|是|否|待定(复用 frontier 语义)
  llm_scores JSONB,                   -- Rotolo 5属性 {novelty,growth,impact,coherence,ambiguity}
  llm_evidence TEXT,
  assessed_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(object_type, object_id, window_month)
)
```

不改 RelationType(55 枚举冻结);ROR 归一产出写 `org_profile` 建议字段+`relation_staging`,人工/阈值确认后落 Neo4j。

## 6. 开发计划(Phase A→E,每 task TDD)

### Phase A 地基修复+扩源+证据链(G1-G9)← **本轮开工**
- A1 修 `_SOURCE_SPECS`:science `event_time`;patent 实体列 `applicant`(Inventor 移 features 解析);attachment 表存在性探测+优雅跳过
- A2 新增 4 源(policy/key_events/industry_report/international_news:title+event_time+实体列)+`industry` 域过滤参数
- A3 `term_stats` 表+migration 0010+提取器写计数(df 非 presence,顺修 G8)
- A4 证据回填:每信号 top-N docs→`evidence_doc_ids`;共现实体→`related_org/person_ids`(名字→profile id 解析,ILIKE+精确两级)
- A5 真共现边:同文档 top 术语对频次→`signal_network_edge(edge_type=co_occurrence, weight=共现数)`
- A6 corpus loader 单测扩:每源 SQL 列名对 DDL 校验(防再漂移)

### Phase B 新兴指标层(G10)
- B1 `emergence_metrics.py` 纯函数:active_entities/new_entrant_ratio/doubling_time/breadth
- B2 TLC:`s_curve_stage`(Gompertz+Logistic AIC 择优)+`haupt_ratio`(专利/申请人增速)
- B3 TEM:share×growth 象限分类(x=全对象均值,y=0)
- B4 IPC 共类:Salton 强度矩阵按年滚动+新对检测(首现年+强度升)
- B5 `tech_emergence_indicator` 表+写入编排(celery 任务,复用 run_async)+查询 API `GET /new-tech/emergence`

### Phase C 颠覆层(G11)
- C1 组合新颖性:文档 IPC 对"历史从未出现"占比(Wang 式,窗口滚动)
- C2 DisruptScore 加权合成(权重入 settings)
- C3 LLM Rotolo rubric validator(复用 gateway+call_with_schema,3 次中位,Top-N 触发)
- C4 `disruption_assessment` 表+API `GET /new-tech/disruption`+celery 任务
- C5 前端 NewTechDiscovery 加"新兴指标/颠覆性"Tab

### Phase D 实体增强(G12-G14)
- D1 ROR 数据下载脚本+rapidfuzz 匹配服务+org 归一任务(建议合并,不自动合并)
- D2 作者消歧规则版:blocking+共作者 Jaccard+机构串相似→合并建议
- D3 项目 LLM 分类→tech_domain(批任务,配额护栏)

### Phase E 管线串联(G4/G15/G16/G17)
- E1 `POST /frontier-tech/scan` 接真 `ScanMonitorService.run_scan`(数据源换 term_stats/emergence/weak_signal;5 scorer 改读真指标)
- E2 子项目3:validated frontier→topic_candidate 生成+评分
- E3 cron 类型 `weak_signal_scan`/`frontier_scan`(_build_registry+_ALLOWED_TASK_TYPES)
- E4 tech-tech P2:TECH_CO_OCCURS builder(同文档 L2 对+共 IPC+Salton 阈值)
- E5 tech-tech P3:TECH_EVOLVES_FROM(同域 filing_date 时序+LLM problem-solution,配额护栏)

### 里程碑
- M1(Phase A):真 8 源语料弱信号端到端,证据+网络真数据
- M2(B+C):新兴指标+颠覆分+LLM 评审全链路,UI 可看
- M3(D+E):实体增强+三层管线全自动(cron)+tech-tech 真挖掘

## 7. 风险与对策
- **语料薄**:policy/events/report/news 只有 title(内容在 features JSON)→ Phase A 先 title,features 抽取列为 A2 可选增强。
- **glm 配额**:所有 LLM 走漏斗末端+llm_call_log+稀疏 cron;统计层零 LLM。
- **Neo4j 类型分裂**(mock=NAME/真挖=VALUE):E4/E5 落库统一用枚举 NAME(TECH_CO_OCCURS 等),TripleWriter 对齐。
- **云栈无 Doris**:全部新能力 gate 在 db_connection 存在+MODE≠readonly。
