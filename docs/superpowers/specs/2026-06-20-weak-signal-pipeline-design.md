# 弱信号识别与三层情报 Pipeline 设计（子项目 1：真弱信号提取 + ingest_ods 串接 + 附件抽取）

- 日期：2026-06-20
- 范围：新技术发现（new_tech_discovery）真弱信号提取算法实现 + 接 ingest_ods 真语料（含附件全文本抽取）+ 为后续「弱信号→扫描→选题」三层 pipeline 打地基
- 课题创新点：**创新点 2 —— 复杂异构数据驱动的弱信号识别**
- 用途：本算法部分后续用于撰写**发明专利**（技术方案 / 创新点 / 实施细节须可复现）

---

## 1. 背景与技术问题

### 1.1 业务背景
系统三层分析层（新技术发现 → 扫描监测 → 选题服务）目前各自独立、由 `demo_analysis.py` 造 mock 数据驱动，**无真实数据流**。要讲清"弱信号→前沿扫描→选题"业务故事，必须让弱信号层吃真数据、跑真算法。

### 1.2 技术问题（专利"要解决的技术问题"）
科技情报领域对"前沿技术"的捕捉普遍存在两类偏差：
1. **只追热点**：基于频次/引用的检测只能发现"已经火"的技术，错过**早期、低强度、尚未被广泛关注**的弱信号（Ansoff 弱信号理论）。
2. **单源局限**：仅依赖论文或专利单一来源，噪声大、易误报，无法交叉印证。

现有公开方法（Kleinberg burst、BERTopic、孤立森林等）各解决单点问题，但**缺乏一个把多源异构语料融合、量化"虽弱但值得关注"程度、并自适应阈值的端到端方法**。

本设计的技术方案针对该问题。

---

## 2. 总体架构（方案 A：ingest 后自动 hook + UI 手动触发）

### 2.1 选定方案
- **附件抽取**：ingest_ods collector 新增「附件抽取阶段」——原始文件（PDF/DOCX）→ 文本抽取 → `clean_content` 落库，作为弱信号语料之一。
- **提取触发**：① ingest_ods 批次完成后**自动 hook**触发弱信号提取（pipeline 本意，ingest 完即出信号）；② UI「触发发现扫描」按钮**手动重跑**（替换现有 demo 桩）。
- **算法**：实现 `WeakSignalExtractor.extract()`（中度：突现 + 新颖度 + 多源多样性 + 增速 + 趋势检验 + NER 实体异常）。

### 2.2 备选方案（已评估，记录在案）
- **B 定时 cron 批处理**：提取与 ingest 解耦，夜间批跑。优点：ingest 路径轻；缺点：不实时，需新增 cron 执行器。**不选**（pipeline 实时性诉求）。
- **C 纯手动**：仅按钮触发。优点：最简；缺点：不自动，违背 pipeline 自动接力本意。**不选**。

### 2.3 数据流（端到端）
```
ODS(Doris) ─ingest_ods─▶ profile 表(tech/org/person/project) + Neo4j 关系
                         │
                         ├─[附件]─▶ 文本抽取(pdfplumber/docx)─▶ clean_content 入库
                         │
                         ▼
            [hook: 批次完成] ──▶ WeakSignalExtractor.extract(corpus)
                                          │
                          突现/新颖/多样/增速/趋势/NER ──▶ 强度量化(4维加权)
                                          │
                          自适应阈值(μ+kσ) 过滤 ──▶ weak_signal 表
                                          │
                          共现关联 ──▶ signal_network_edge 表
                                          │
                          (后续子项2) ──▶ scan_monitor 前沿候选
                                          │
                          (后续子项3) ──▶ topic_selection 选题
```

---

## 3. 语料与预处理

### 3.1 语料源（多源异构 —— 创新点之一）
| 源 | ODS 表 | 文本字段 | 时间字段 | 语言 |
|----|--------|----------|----------|------|
| 论文 | ods_science_literature | title / abstract / keyword | pubdate | 英文 |
| 专利 | ods_invention_patent_cn | title / applicant / inventor | filing_date | 中文 |
| 市场 | ods_market_analysis_cn | title / purchaser / event_time | event_time | 中文 |
| 附件 | 原始文件→clean_content | 全文本 | 文件所属记录时间 | 中/英 |

多源 = 论文（学术前沿）+ 专利（产业化意图）+ 市场（资本/采购动向）+ 附件（深度全文），覆盖**学术—产业—资本—全文**四维，互为印证。

### 3.2 附件文本抽取（**独立 spec，见 `2026-06-20-attachment-extraction-design.md`**）
附件（PDF/DOCX 全文 → `clean_content`）作为弱信号语料之一，但其抽取流程（文件解析/OCR/清洗/入库/幂等）**单独成 spec 与实现**。本 spec 将附件 `clean_content` 视为既有输入依赖，不重复展开。

### 3.3 文本预处理（分词 / 归一）
- 中文：jieba 分词 + 自定义科技词表 + 停用词过滤。
- 英文：小写化 + 词形还原（lemmatize）+ 停用词过滤。
- 术语词典：从已有 profile 的 tech_name / keyword 构建领域词典，优先保留术语整词（避免"量子计算"被切碎）。
- 时间窗：按月（可配）切片，每源每窗统计词频。

---

## 4. 弱信号提取算法（核心 —— 专利技术方案详记）

### 4.1 候选词项构建
对每个时间窗 `t` 的语料，构建候选词项集合 `V`：
- 论文：keyword 字段 + abstract 的领域术语抽取。
- 专利：title 术语 + ipc 类别名 + applicant/inventor（作命名实体）。
- 市场：title 术语 + purchaser。
- 附件：clean_content 的 TF-IDF top-N 术语 + NER 实体。

候选 = 术语词项 ∪ 命名实体。每候选 `k` 在窗 `t` 内统计：文档频 `df(k,t)`、词频 `tf(k,t)`、出现源集合 `S(k,t)`。

### 4.2 关键词突现检测（Burst Detection）
**目标**：识别在近期窗口词频**突增**的词项（Kleinberg burst 思想的简化可实现版）。

对词项 `k`，设历史基线期望频次 `E[k] = mean(df(k, ·) over history)`，当前窗观测 `df(k,t)`：
```
burst(k,t) = max(0, (df(k,t) − E[k]) / (σ[k] + ε))
```
其中 `σ[k]` 为历史频次标准差，`ε` 防除零。`burst>θ_burst`（默认 2.0，即超出基线 2σ）判定为突现。

> 与原 Kleinberg（基于隐状态自动机的概率突现）相比，本方案用**标准化突现比 z-score**，计算轻、可解释、无需训练，适合流式增量更新；在发明专利中作为"突现检测的具体实施方式"。

### 4.3 新颖度 Novelty
**目标**：词项越"新冒头"越值得关注。
```
novelty(k) = 1 − clamp( H[k] / W , 0, 1 )
```
`H[k]` = 词项 `k` 在历史 `W` 个窗中已出现的窗数；从未出现 → novelty=1（全新），长期存在 → 趋近 0。

### 4.4 多源多样性 Diversity（创新点之一）
**目标**：词项被**多个异构源**印证，可信度高（单一源易噪声）。
按源类型分布 `p_s(k) = df(k, s) / Σ_s' df(k, s')`（s ∈ {论文, 专利, 市场, 附件}），用**Shannon 熵归一化**：
```
diversity(k) = ( −Σ_s p_s(k)·log p_s(k) ) / log(|S|)
```
单源 → 0；均匀四源 → 1。**跨源印证**是本方法区别于单源检测的关键创新。

### 4.5 增速 Velocity
**目标**：词项频次**上升速率**。
对最近 `m` 个窗（默认 3）的频次序列做**归一化线性回归斜率**：
```
velocity(k) = clamp( slope(df(k,·) recent m) / |max_slope| , 0, 1 )
```
辅以 **Mann-Kendall 趋势检验**（非参数，不要求数据分布）：计算 Kendall τ，`τ > τ₀`（默认 0.6）视为显著上升趋势；不显著则 velocity 折半（惩罚不确定趋势）。

### 4.6 一致性 Coherence
**目标**：信号在多源间**语义/时间一致**（同一窗口多源同时抬头）。
```
coherence(k) = |{ s : df(k,t,s) 增长 }>θ| / |S|
```
即当前窗内源频次同时增长的源占比（多源同涨 = 强一致性）。

### 4.7 强度量化（4 维加权融合 —— 创新点之一）
融合上述 4 个 [0,1] 维度成综合强度（已实现于 `SignalStrengthQuantifier`）：
```
strength(k) = 0.30·novelty + 0.25·coherence + 0.20·diversity + 0.25·velocity
```
权重设计依据：新颖度（创新萌芽）最重 0.30；一致性与增速（可信 + 势头）各 0.25；多样性（广度）0.20。权重可配（`settings`）。

> **创新点**：业界弱信号/新兴主题检测多以**单一频次或突现**为强度；本方法提出**"虽弱但值得关注"的四维加权量化**（新颖×一致×多样×增速），把"弱"从"频次低"重定义为"多维信号聚合值"，更鲁棒、可解释。

### 4.8 自适应阈值（Adaptive Threshold）
不设固定阈值（避免数据量变化时失效）。对当前 `weak_signal` 表全量 strength 分布算：
```
threshold = μ(strength) + k·σ(strength)    （k 默认 1.0，可配）
```
仅 `strength ≥ threshold` 的候选落库为弱信号（已实现于 `adaptive_threshold.py`）。`k` 调高=更严（少数精），调低=更宽。

### 4.9 命名实体异常（NER Anomaly）
对候选实体集合（applicant/inventor/机构/人名/技术名），用 **z-score 异常**检测"新出现且高频"实体：
```
anomaly(e) = (df(e,t) − μ_e) / (σ_e + ε)
```
`anomaly > θ_a`（默认 2.5）的实体视为异常冒头实体，附加进弱信号 `related_*_ids`（关联技术/机构/人员）。

### 4.10 信号关联网络（Signal Network）
- **共现边**：同一文档/窗内共同出现的实体对 `(a,b)`，边权 = 共现频次。
- **资助/引用边**：复用 ingest_ods 已有关系（ORG_FUND / citation）。
- 落 `signal_network_edge(source_id, target_id, edge_type, weight)`；前端 G6 渲染（节点可点跳转，已实现 #2）。
- （中度方案不做图嵌入/社区发现，留作后续增强；当前用共现 + 已有关系足够支撑关联网络视图。）

### 4.11 端到端提取流程（`WeakSignalExtractor.extract` 实现纲要）
```
extract(domain?, period_from, period_to) -> list[WeakSignal]:
  1. 拉取期内语料（4 源 + 附件 clean_content），按月分窗
  2. 预处理（分词/归一/术语词典），构建候选词项 V 与实体 E
  3. 对每个候选 k：
       算 burst / novelty / diversity / velocity / coherence
       strength = 4 维加权
  4. adaptive threshold(μ+kσ) 过滤
  5. NER 异常实体附加 related_*_ids
  6. 构建共现关联网络 → signal_network_edge
  7. 落 weak_signal 表（去重：keyword 集合哈希）
  return signals
```

---

## 5. 创新点（发明专利"发明点"）

1. **多源异构融合的弱信号识别**：论文+专利+市场+附件四类异构语料统一进入候选空间，跨源印证（diversity + coherence），区别于单源检测。
2. **"虽弱但值得关注"四维加权强度量化**：把弱信号强度从单频次重定义为 `novelty/coherence/diversity/velocity` 加权聚合，更鲁棒可解释。
3. **自适应阈值**：基于实测分布 `μ+kσ` 动态阈值，随数据量自适配，免人工调参。
4. **突现-趋势-异常三检测融合**：z-score 突现 + Mann-Kendall 趋势 + NER z-score 异常，多角度交叉确认候选。
5. **附件全文本深度抽取**：把 PDF/DOCX 全文纳入语料（多数系统只用结构化字段），捕获 title/abstract 之外的深度信号。
6. **ingest-pipeline 实时接力**：ingest 完成即自动触发提取，弱信号→扫描→选题自动流（区别于离线批处理）。

---

## 6. 组件与接口

### 6.1 新增 / 改造
| 组件 | 位置 | 职责 |
|------|------|------|
| `AttachmentExtractor` | 见独立 spec `2026-06-20-attachment-extraction-design.md` | PDF/DOCX → clean_content（外部依赖） |
| `WeakSignalExtractor.extract` | `new_tech_discovery/services/weak_signal_extractor.py`（实现桩） | 端到端提取（§4.11） |
| 突现/趋势/NER 子计算 | 复用/补 `anomaly_detector.py` `trend_recognizer.py` | §4.2/4.5/4.9 |
| ingest hook | `ingest_ods/collectors/sql_warehouse.py` 批次后 | 自动触发 extract |
| 路由 | `new_tech_discovery/api/routes_signals.py` 触发端点 | 替 demo 为真 extract |

### 6.2 关键签名
```python
class WeakSignalExtractor:
    async def extract(self, *, domain: str | None,
                      period_from: date, period_to: date) -> list[WeakSignal]: ...

class AttachmentExtractor:
    async def extract_text(self, *, path: str | bytes, mime: str) -> str:  # -> clean_content
```

---

## 7. 实施步骤（高层次，后续 writing-plans 细化）
1. **附件抽取**：见独立 spec（PDF/DOCX→clean_content），本 spec 视其为前置依赖。
2. 语料预处理（分词/术语词典/分窗）。
3. 候选词项 + 各维度计算（burst/novelty/diversity/velocity/coherence）。
4. 强度量化 + 自适应阈值 + NER 异常。
5. 关联网络构建。
6. `extract()` 串接 + 落库。
7. ingest hook 自动触发 + 路由手动触发（替 demo）。
8. 单测（各维度公式）+ 集成（真语料端到端）。

---

## 8. 有益效果（专利"有益效果"）
- 更早发现前沿技术（弱信号先于热点）。
- 多源印证降误报、提可信。
- 自适应阈值免调参、随数据量稳健。
- 四维可解释强度，支持情报分析师理解"为什么值得关注"。
- 附件全文纳入，信号覆盖更全。

---

## 9. 后续子项目（本 spec 不含）
- 子项 2：弱信号 → 扫描监测（信号聚合为前沿候选，喂 fusion + LLM 验证）。
- 子项 3：扫描监测 → 选题（验证过的前沿 → 选题候选 + 评分 + 人工评审）。
- 增强：图嵌入 / 社区发现 / BERTopic 主题模型 / 自编码器异常（中度方案留口，未实现）。
