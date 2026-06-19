# 画像数据质量评分 — 设计文档（规则型，ISO 25012 对齐）

- 日期：2026-06-19
- 范围：把 ingest_ods 的 LLM Scorer 重写为**确定性规则算法**；对齐 ISO/IEC 25012 + DAMA 评分法；可选加复合 DQI。
- 触发：现 LLM scorer（glm-4.7 打 veracity/timeliness）慢（~90s/实体）+ 脆（JSON 解析失败 → 评分归 0，实测新画像 veracity/timeliness=0）；ingest 被它卡住。业界（IBM Purview / Microsoft Purview / Ataccama / Collibra）评分一律规则/比率型，不用 LLM。
- 状态：决策已定（§2），待 writing-plans → 实现。

---

## 1. 现状与问题

- `metaprofile/ingest_ods/services/scorer.py`：`Scorer.score()` 用 LLM 打 veracity+timeliness，返 `{veracity_score, timeliness_score, data_as_of}`；失败兜底 0.0。
- completeness 在别处算（`shared/enrich` 的 completeness scorer，按 `_FIELD_SPEC` 字段填充率）——**已是规则型**。
- 三处 profile ORM 列已有：`completeness / veracity_score / timeliness_score / data_as_of`（migration 0003 加）。
- 问题：①LLM 评分慢（~90s/实体，ingest 50 行 ~75min）；②JSON 解析失败 → 评分 0；③completeness 与 veracity/timeliness 不一致（前者规则、后者 LLM）。

## 2. 采用的标准与维度（决策）

**参考框架**：ISO/IEC 25012（数据质量模型，定义"评什么"）+ DAMA-DMBOK 六维法（定义"怎么算"= 比率 + 加权）。业界工具（IBM/Microsoft/Ataccama/Collibra）均照此。

**v1 采用 3 个维度**（对齐现有 3 列，最小改动打通）：

| 现有列 | ISO 25012 维度 | 含义 | 算法类型 |
|---|---|---|---|
| `completeness` | Completeness | 期望字段填充率 | 规则（复用现有）|
| `veracity_score` | **Credibility + Accuracy** | 来源可信 + 权威信号 + 字段一致性 | 规则（新写）|
| `timeliness_score` | Timeliness / Currentness | 数据时效（按 `data_as_of` 衰减）| 规则（新写）|

**v2 候选（本 spec 不实现，留扩展）**：Consistency（跨源一致）、Uniqueness（去重）、Validity（枚举/格式合规）—— 需要跨表比对/去重索引，scope 更大，单列后续。

**复合分 DQI（新增，可选）**：`dq_index = Σ wᵢ·维度ᵢ`，默认权 completeness 0.4 / veracity 0.3 / timeliness 0.3（Σ=1.0，**可调**）。作为派生展示分，存新列 `dq_index`（nullable）或前端读时计算。本 spec 采"存列"以便排序/筛选。

## 3. 算法（确定性，零 LLM）

### 3.1 Completeness（复用现有逻辑）
- 公式：`filled_count / expected_count`，`expected_count` = 该 profile_type 的 `_FIELD_SPEC` 总字段数；`filled_count` = 非空字段数。
- 已在 `shared/enrich` 实现，Scorer 调用同一函数，不重写。

### 3.2 Credibility / veracity（新写，规则）
```
veracity = clamp[0,1](
    source_trust_weight                       # 来源基线权重(下表)
  + authority_bonus                           # 权威信号加分
) * consistency_factor                        # 一致性乘子
```
- **source_trust_weight**（来源可信度表，**可调**）：
  | 来源 source_method / 通道 | 权重 |
  |---|---|
  | ODS Doris 官方库（sql_warehouse 抽取）| 0.90 |
  | LLM 补全（enrich llm_enrich）| 0.70 |
  | 批量导入 JSON（bulk_import / 手工）| 0.60 |
  | UGC / 网页抓取 | 0.40 |
  - 判定：`source_rows[0].source_method` 或 collection 通道（collection_task.source_type）。
- **authority_bonus**（每项 +0.05，cap +0.15）：有 DOI / 有引用(citation) / 有官方编号(usc_code/orcid/patent_no/project_no)。
- **consistency_factor**：跨字段一致性检查通过=1.0；任一失败=0.85。检查项（按 profile_type 选）：日期顺序合理（invention≤application）、必填名非空、枚举值合法。
- 缺来源信息 → 基线 0.50。

### 3.3 Timeliness（新写，规则）
```
age_days = (today - data_as_of).days          # data_as_of = source_rows 最新 update_time/event_time
timeliness = clamp[0,1]( exp(-age_days / 180) )   # 180 天半衰期,可调
```
- 无 `data_as_of` → `timeliness = 0`（时效未知=最差），**不**用 LLM 兜底。
- 衰减曲线选指数（比线性更贴合"新鲜度直觉"）；半衰期 180 天 **可调**（settings.thresholds.timeliness_halflife_days）。
- `_latest_as_of()`（scorer.py 现有）复用。

### 3.4 复合 DQI
```
dq_index = 0.4*completeness + 0.3*veracity + 0.3*timeliness     # 权重可调
```
四舍五入 4 位。写 `dq_index` 列。

## 4. 组件设计

**`metaprofile/ingest_ods/services/scorer.py` 重写**：`RuleScorer`（确定性，无 `llm` 依赖）。
```python
class RuleScorer:
    def __init__(self): pass   # 无 llm
    async def score(self, profile_type, attrs, source_rows) -> dict:
        data_as_of = _latest_as_of(source_rows)
        completeness = completeness_score(profile_type, attrs)      # 复用 shared.enrich
        veracity = _credibility(profile_type, attrs, source_rows)   # §3.2
        timeliness = _timeliness(data_as_of)                        # §3.3
        dq = 0.4*completeness + 0.3*veracity + 0.3*timeliness
        return {"completeness": completeness, "veracity_score": veracity,
                "timeliness_score": timeliness, "data_as_of": data_as_of,
                "dq_index": round(dq, 4)}
```
- 接口签名不变（`score(profile_type, attrs, source_rows) -> dict`），调用方（orchestrator）零改动。
- `orchestrator.py`：`Scorer(llm=llm)` → `RuleScorer()`；移除 scorer 的 llm 注入。
- 抽 `_credibility` / `_timeliness` 到 `metaprofile/ingest_ods/services/quality_rules.py`（纯函数，可单测）。
- source_trust 权重表 + timeliness 半衰期 → `shared/config/settings.py` 的 `thresholds`（可调，不硬编码）。

**schema/存储**：
- `LLMProviderConfigORM` 无关。profile ORM 4 列已存在（completeness/veracity_score/timeliness_score/data_as_of）。
- 新增 `dq_index: FLOAT` 列（4 profile 主表）→ migration 0005（`ALTER TABLE ... ADD COLUMN dq_index FLOAT`）。
- response schema（4 画像 `*_response.py`）暴露 `dq_index`（output-only）。

**LLM 边界**：评分完全去 LLM。LLM 仅保留于：抽取富化、关系挖掘（content_miner）、enrich 字段补全。与 §1 现状对齐（completeness 本就规则）。

## 5. 收益与权衡

| | 现(LLM) | 新(规则) |
|---|---|---|
| 速度 | ~90s/实体 | 毫秒 |
| 可靠 | JSON 失败→0 | 确定性,不归零 |
| 成本 | 每条 LLM 调用 | 0 |
| 标准 | 自创 | ISO 25012 + DAMA |
| 可解释 | 黑盒 | 公式可审计 |

权衡：规则型 veracity 是**启发式近似**（来源权重+信号），不如 LLM 对"语义合理性"的判断深；但业界实践证明对画像数据足够，且可叠加（v2 加 Accuracy 抽样校验）。主观合理性判断留给 enrich 的 LLM 补全 + 人工复核，不进评分主路径。

## 6. 测试（确定性，好测）

- `quality_rules` 单测：
  - `_timeliness`：age=0→1.0；age=180→0.5；age=∞→0；无 data_as_of→0。
  - `_credibility`：ODS+DOI→≈0.95；UGC 无信号→0.40；日期逆序→×0.85。
  - `completeness`：全填→1.0；半填→0.5。
  - `dq_index`：权重加权和正确。
- `RuleScorer.score` 集成：mock source_rows → 期望 dict。
- 回归：现有 ingest_ods 测试（scorer 用例）改用 RuleScorer，断言数值而非 LLM mock。

## 7. 关键文件

- 改：`ingest_ods/services/scorer.py`（重写为 RuleScorer）、`ingest_ods/services/orchestrator.py`（去 llm 注入）、`shared/config/settings.py`（thresholds 加权表/半衰期）、4 画像 `*_response.py`（暴露 dq_index）。
- 新：`ingest_ods/services/quality_rules.py`（纯函数）、migration 0005（dq_index 列）。
- 复用：`shared/enrich` completeness scorer、scorer 现有 `_latest_as_of`。

## 8. 非目标（YAGNI）

- 不实现 Consistency/Uniqueness/Validity（v2）。
- 不引入第三方 DQ 工具/库（自写规则足矣，零新依赖）。
- 不回填历史 mock 数据的 dq_index（仅新 ingest/enrich 数据计算；历史可一次性回填脚本，后续）。
- 不改 LLM 在抽取/关系/enrich 的用途（仅评分去 LLM）。

## 9. 部署/验收

- 重建 backend（scorer 重写）+ 跑 migration 0005（加列）。
- 重跑 ingest_ods smoke（datasource 11，max_rows 小）：新画像 veracity/timeliness/dq_index **非 0**（规则算出），ingest 毫秒级完成。
- 验收：一条新画像 4 分都有合理值；ingest 50 行 < 30s（对比原 ~75min）。
