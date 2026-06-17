# ODS 数据 → 四类画像 抽取管线 设计

- 日期：2026-06-17
- 状态：设计稿（待评审）
- 作者：Claude Code + 用户
- 相关 memory：`ods-data-source` / `ods-mirror-mysql` / `project-data-write-path` / `project-cross-profile-design` / `project-profile-ui-upgrade`

---

## 1. 背景与目标

从产业技术情报数据仓库 **ODS `ods_zbzx`**（云上 Apache Doris，9030 端口 MySQL 协议）中，**抽取并构建四类关键目标画像**：

- **Tech（技术）** · **Project（项目）** · **Org（机构）** · **Person（人员）**

两条抽取路径：
- **表→表**：ODS 结构化字段直接映射到画像字段（简单、量大）。
- **内容→表**：附件正文（`clean_content` 全文）经 **LLM 挖掘**出四类实体 **+ 关系**（重点，必用 LLM）。

并支持**定期批量更新**（存量首跑全量 + 后续增量）。

**生产代码部署到云端运行，直接读云 Doris**（同机房，快）；**本地 Doris 仅用于开发/测试**，同步一个够用的子集即可（非全库镜像）。两源同方言，提取器零分叉。

---

## 2. 数据源摸底（2026-06-17 实测）

连接：`10.242.0.1:9030` user `gz_kt5` 只读 `ods_zbzx`。**39 表 / 5.48 亿行**。

| 表 | 行数 | 目标画像 | 关键字段 / 备注 |
|---|---|---|---|
| `ods_company_basic_info` | 429M | Org | 32 结构化字段，**无 features 列**：company_id/usc_code/company_name/legal_person_name/category_name/province/reg_capital/pension_count/estiblish_time |
| `ods_market_analysis_cn` | 36.4M | Project+Org | title/purchaser/region/announcement_type/amount；features: agency_name/budget_amount/project_contact/bid_opening_time/release_time |
| `ods_invention_patent_cn` | 29.5M | Tech+Org+Person | title/applicant/ipc_type/legal_status/is_authorized/filing_date；features: **Inventor(分号人名)**/Patent_number/Publication_number/Open_day |
| `ods_market_analysis_attachment_cn` | 26.3M / 501GB | (附件) | raw_content(HTML)/clean_content(全文) |
| `ods_science_literature` | 6.85M | Tech+Person | title/authors(JSON)/keyword/abstract；features: doi/citation_count/orcid_pub/pubdate/doctype/pub |
| `ods_science_literature_attachment` | 3.46M / 458GB | (附件) | clean_content 全文 |
| `ods_strategic_policy_cn` | 3.81M | Tech+Org | title/policy_source；features: StrCreateTime |
| `ods_industry_report_cn` | 1.9M | Tech+Org | title/publishing_organization |
| `ods_international_news` | 1.8M | 弱信号 | features: impact + ETL 字段(quality_score/process_status) |
| `ods_financial_info_cn` | 881K | 辅助 | features: impact(正/负) |
| `ods_oversea_company_info` | 234K | Org | 海外企业(国家/城市/行业) |
| `ods_talent_info_cn` | **11K** | **Person 唯一直接源** | full_name/education/job_title/employer；features: sex/mail/unit/discipline/graduatedUniversity |
| `ods_key_events_cn` | 6.7K | 时间线 | title/event_time |
| `ods_item_category` | 4432 | 字典 | 国民经济行业分类 5 级(category_code/category_name) |
| `*_global`（18 表） | 0 | — | 全空，跳过 |

**公共字段**（除 company/oversea/item 外的主表）：`id, event_time, create_time, update_time, collect_source_id, task_id, original_id, collect_source_name, industry, original_table, url, minio_path_file, minio_path_raw, features(json)`。

**`features` JSON = 半结构化金矿**（旧 memory 标"未抽样"，本次已抽样确认结构，见上表）。

**附件表统一结构**：`id, event_time, create_time, update_time, original_table(varchar), raw_content(text,HTML), clean_content(text,全文), other_content(text), other_content2(text), original_id(int)`。注意：早期行 `clean_content` 为 NULL → 内容挖掘须 `WHERE clean_content IS NOT NULL`。

**身份键（实体合并/消歧用）**：
- Org：`company_id` | `usc_code` | name 归一化
- Person：`orcid`(science features) | `email`(talent/patent features) | `full_name+employer`
- Tech：`Patent_number`(patent features) | `doi`(science features) | `title+ipc`
- Project：`title + purchaser + region`

---

## 3. 需求与约束（用户确认，共 10 条）

1. 抽 4 类画像（Tech/Project/Org/Person）。
2. 两路径：结构化直抽 + 附件 LLM 文本挖掘。
3. 调度：**cron 定时 + 手动实时**两种触发。
4. **存量（首跑全量）+ 增量**都要覆盖。
5. 任务粒度灵活：4 类合抽 或 分抽，不限制。
6. **LLM 走系统配置接口**（`llm_provider_configs` + `LLMGateway`），不自建。
7. **数据源走系统配置**（`data_source_configs`）。
8. **云(Doris) + 本地(Doris) 两源都配进系统**；本地亦改造成 Doris，统一机制，仅地址不同。
9. **附件文本抽 4 类画像 + 关系(relations) 是重点，必用 LLM**。
10. 四点细则：
    1. 定时任务：可调度、可手动执行、**任务间并行控制**。
    2. **批次大小 ↔ 并行度耦合**。
    3. **表→表**：简单，但 LLM 介入判 **真实性(veracity) + 时效性(timeliness)**。
    4. **内容→表**：LLM 抽信息 + 判真实性/时效性。

---

## 4. 关键决策（已锁定）

| 决策点 | 选择 | 理由 |
|---|---|---|
| 实体模型 | **混合：规范键优先 + LLM 消歧** | 目标 schema 实体中心；有键直接归并，无键 LLM 判同异，准且可扩 |
| 增量识别 | **`update_time` 高水位 + upsert** | 新装/重装行都中；首跑 watermark=null=全量；`id` keyset 兼作大表分页避 OOM |
| LLM 边界 | **两阶段：结构化全量(零/轻 LLM) + LLM 选择性** | 547M 行 + 1.1TB 附件，全跑 LLM 不可行；LLM 只用于消歧/字段合成/薄实体挖附件/关系 |
| DB 引擎 | **云+本地统一 Doris** | 同方言，提取器零分叉，仅 host 不同 |
| 凭据存储 | **独立 `db_connections` 注册表** | 集中、可轮换、多源共用，不入 config_json 明文 |
| 质量评分落库 | **profile 主表加 3 列** `veracity_score/timeliness_score/data_as_of` | 头等质量维度，可索引可查询，优于埋 JSONB |

---

## 5. 架构总览

解耦分阶段流水线 + 批次工作池，无新基础设施（复用 `data_source_configs`/`collection_tasks`/`collector_service`/profile `/import`/`LLMGateway`）。

```
                  ┌──────────── DataSourceConfig (sql_warehouse) ────────────┐
                  │  云 Doris 9030  ·  本地 Doris 9030  (db_connections 引用) │
                  └────────────────────────┬──────────────────────────────────┘
                                           │ trigger_collection (cron / 手动)
                                           ▼
        ┌───────────────────── CollectionTask (status/records_*/log) ────────────────────┐
        │                                                                                │
        │   BatchOrchestrator  ── id-keyset 拉批 (batch_size = workers × rows/worker) ──► │
        │   asyncio.Semaphore(workers)  并发受 LLM RPS 约束                               │
        │                                                                                │
        │   ① Extract(表→表)    SQL(watermark+id-keyset) → staging_raw   [零/轻 LLM]      │
        │   ② ContentMine(内容→表) attachment.clean_content → LLM 抽实体+关系  [LLM 核心]  │
        │   ③ Resolve/Merge    规范键优先 → 否则 name 归一 → LLM 消歧 → upsert            │
        │   ④ Score            LLM 判 veracity + timeliness                              │
        │   ⑤ Write            profile ORM upsert + relations→Neo4j + EntityChangeLog    │
        │                                                                                │
        │   每批完成 → 刷 last_id/last_watermark 到 config_json + CollectionTask 计数      │
        └────────────────────────────────────────────────────────────────────────────────┘
```

模块落位（新增，遵循现有 `metaprofile/<domain>/` 分层）：

```
metaprofile/ingest_ods/
├── domain/
│   ├── orm_models.py        # staging_raw / ingest_errors / db_connections / relation_staging
│   └── mappings.py          # 表→表 字段映射声明（每源表→profile 字段）
├── services/
│   ├── orchestrator.py      # BatchOrchestrator：拉批 + Semaphore 并发 + 断点续
│   ├── extractor.py         # 阶段① 表→表 SQL 抽取 → staging_raw
│   ├── content_miner.py     # 阶段② 附件 LLM 抽实体+关系
│   ├── resolver.py          # 阶段③ 实体合并/消歧
│   ├── scorer.py            # 阶段④ veracity/timeliness LLM 评分
│   ├── writer.py            # 阶段⑤ profile upsert + Neo4j 关系 + 变更日志
│   └── watermark.py         # last_id/last_watermark 存取
├── collectors/
│   └── sql_warehouse.py     # 新 source_type="sql_warehouse" 适配器（接入 collector_service）
└── llm/
    └── prompts.py           # 抽取/消歧/评分 各 prompt + pydantic 结构化输出 schema
```

`collector_service.trigger_collection` 增 `elif source_type == "sql_warehouse"` 分支 → 调 `ingest_ods.orchestrator.run(task, source)`。

---

## 6. 数据源与配置

### 6.1 `db_connections` 注册表（新）

```python
class DBConnectionORM(Base, TimestampMixin):
    __tablename__ = "db_connections"
    id            # pk
    name          # str128 唯一，如 "ods-cloud-doris" / "ods-local-doris"
    dialect       # str16  固定 "doris"（预留）
    host, port    # 10.242.0.1 / 9030 ; 本机 FE / 9030
    database      # ods_zbzx
    username      # gz_kt5
    password_enc  # text，对称加密（key 来自 settings.secret_key），非明文
    charset       # utf8mb4
    pool_size     # int，默认 8
    read_only     # bool，默认 True（仅抽，禁写）
    is_enabled    # bool
```

### 6.2 `data_source_configs` 复用

`source_type = "sql_warehouse"`，`config_json` 示例：

```jsonc
{
  "db_connection_id": 1,                 // → db_connections
  "table_set": ["ods_company_basic_info","ods_invention_patent_cn","ods_science_literature",
                "ods_market_analysis_cn","ods_talent_info_cn","ods_strategic_policy_cn",
                "ods_industry_report_cn","ods_key_events_cn"],
  "profile_types": ["tech","org","person","project"],   // ["all"] 即全部，内部 fan-out
  "mode": "both",                        // structured_only / content_mine / both
  "enable_relations": true,
  "watermark_col": "update_time",
  "last_watermark": null,                // null=全量首跑；增量由 orchestrator 刷（全局 update_time，跨表）
  "last_id": {},                         // 按表命名空间：orchestrator 读写 "last_id:{table}" 键
                                         //   例 "last_id:ods_company_basic_info"
                                         //   多表 source 不互覆盖/跳过（C2 修正）
                                         //   单 "last_id" 旧写法已废弃——多表会碰撞静默跳表
  "batch_size": 1000,                    // ≈ workers × rows_per_worker
  "workers": 8,                          // 并发度，受 llm_rps 约束
  "rows_per_worker": 20,
  "llm_role_extract": "extraction",      // → llm_provider_configs.model_role
  "llm_role_generate": "generation",
  "content_mine_filter": {               // 附件挖掘触发条件（控成本）
     "only_when_structured_thin": true,  // 结构化填充率 < 阈值才挖附件
     "min_clean_len": 200,
     "sample_max_per_entity": 3          // 每实体最多取 N 段喂 LLM
  }
}
```

注册两条 DataSourceConfig：**ODS-云-Doris**、**ODS-本地-Doris**，仅 `db_connection_id` 与 host 不同。

---

## 7. 流水线各阶段

### ① Extract（表→表，零/轻 LLM）
- 输入：`db_connection` + `table_set` + watermark。
- SQL：`SELECT <投影列> FROM <table> WHERE id > :last_id ORDER BY id LIMIT :batch_size`；增量额外 `AND update_time > :last_watermark`。**禁全表 `SELECT *`/`ORDER BY id` 无 LIMIT**（memory 教训：大表 OOM）。
- 复用 `_load_chunked_big.py` 验证过的安全模式：pymysql 流式 `SSCursor` + 独立连接取数。
- 字段映射（见 §11）→ 写 `staging_raw`，逐源行带 `source_table/source_id/extracted_at/raw_payload(json)`。
- LLM 仅做轻量真实性/时效性 sanity（值是否矛盾/明显脏），重评判留阶段④。

### ② ContentMine（内容→表 + 关系，LLM 核心）
- 触发条件受 `content_mine_filter` 控制（控 1.1TB 成本）：结构化薄 / `enable_relations` / 显式 mode。
- 取附件：`SELECT original_id, clean_content FROM <table>_attachment[_cn] WHERE clean_content IS NOT NULL AND original_id IN (:batch_ids)`。注意 `original_id` 与主表 `original_id` 关联（非 `id`）。
- 长 clean_content 分块（窗口 ~4000 字符，复用 `_ENRICH_MAX_CONTEXT_CHARS`）；可选 embedding RAG 检索相关段再喂 LLM。
- LLM 结构化输出（pydantic 强制）：
  ```python
  class MinedEntity(ProfileBase):
      type: Literal["tech","org","person","project"]
      name: str
      attrs: dict              # 该类型可填字段
      veracity_hint: float     # 0-1，模型自评被文支撑程度
      as_of: date | None       # 文中提及的时间
  class MinedRelation(ProfileBase):
      subject_name: str; subject_type: str
      object_name: str; object_type: str
      predicate: str           # 如 研发/隶属/中标/合作/引用
      evidence: str            # 原文片段（可追溯）
      confidence: float
  ```
- 产出写 `staging_raw`(实体) + `relation_staging`(关系)。

### ③ Resolve/Merge
- 规范键优先：从 raw_payload/features 提 `company_id|usc_code|orcid|email|Patent_number|doi|title+ipc` → 直接归并到现有 profile（PK 命中即 upsert）。
- 无键：name 归一化（去括号/统一全半角/英文小写/去"有限公司"等后缀试匹配）→ 候选簇 → **LLM 批判同异**（一批多对，省 token）。
- 跨源贡献聚合：如某公司在 company_basic_info + patent.applicant + market.purchaser 都出现 → 合一 Org，子表累加（outputs/fundings/activities）。
- upsert profile 主表 + 子表（milestones/fundings/outputs/activities/...）。

### ④ Score（真实性 + 时效性，LLM）
- 每个实体（含合并后）调 LLM 评：
  - **veracity_score**：提取主张是否被源文本支撑 / 是否自相矛盾 / 源可信度（专利>新闻>网页）。
  - **timeliness_score**：基于 `data_as_of` 新鲜度衰减 + LLM 判信息是否仍当前。
  - **data_as_of**：该实体最新源 `update_time`/`event_time`。
- 低 veracity（< review 阈值）→ 标记待人工复核（复用现有 review 机制 + `EntityChangeLogORM`）。

### ⑤ Write
- profile ORM upsert（tech/org/person/project 主表 + 子表）。
- relations → Neo4j（复用现有 relation 写路径，见 memory `project-data-write-path`：Neo4j 独占关系）+ `relation_staging` 留审计。
- 写 `EntityChangeLogORM` 审计。
- 刷 watermark/last_id + CollectionTask 计数。

---

## 8. 批次与并行编排（约束 10①②）

- **拉批**：`BatchOrchestrator` 用 id-keyset，`WHERE id > last_id ORDER BY id LIMIT batch_size`。雪花 id 非连续 → 仅作游标不复用步长（同 memory 结论）。
- **并发**：`asyncio.Semaphore(workers)`。**`batch_size = workers × rows_per_worker`**（默认 1000 = 8 × 125 阶近，可配）。每 worker 处理一批子集。
- **LLM 限速耦合**：`workers ≤ llm_rps`（LLMGateway 已有令牌桶，workers 上限不再加 RPS 压力；超 RPS 自动排队）。
- **任务间并行控制**：
  - 同 `profile_type` 的多源 → **互斥**（写同表冲突），排队。
  - 不同 `profile_type` → **可并行**（独立表）。
  - 实现：进程内 `_active_types: set[str]` 忙等锁——同 `profile_type` 批 serialize，跨 type 并行。**注意 `_active_types` 是进程局部**，不跨进程安全（多 worker 进程部署需另上 DB 行锁）。
  - `profile_types=["all"]` 一源 → 内部 fan-out 4 个 orchestrator（4 profile_type 并行，各管自己表）。
- **断点续 + 原子提交**（C3 修正）：
  - 每批 done 落 watermark 到 config_json：`last_watermark`（全局）+ `last_id:{table}`（按表，见 §6.2）。
  - **watermark 写入位于 `_process_batch` 内、`await session.commit()` 之前**——即 watermark 前进与 profile 写入在同一事务内原子提交。崩溃不会出现 watermark 已前进但 profile 未落库的分歧（反之亦然）。
  - kill/换网/休眠重启从断批继续。
  - **未映射表跳过**：`table_set` 中 `get_mapping(table) is None` 的表 `continue` + 日志记录（不静默拉了又丢）。
  - **禁 `SELECT COUNT(*)`**（活跃写入下卡死，memory 教训）；进度看 `last_id` 推进 + info_schema `TABLE_ROWS` 近似。

---

## 9. 两条抽取路径（约束 10③④）

| 路径 | 来源 | 机制 | LLM 角色 |
|---|---|---|---|
| 表→表 | ODS 结构化列 | 字段映射 → staging → resolve → score → write | 判真实性(值合理/矛盾) + 时效性(event_time 判当前有效) |
| 内容→表 | attachment.clean_content | LLM 抽实体+关系三元组 → staging → resolve → score → write | 核心：信息抽取 + 真实性 + 时效性 + 关系 |

两路径产出同一 `staging_raw`/`relation_staging`，后续 ③④⑤ 共享，**消除分叉**。

---

## 10. 质量评分（真实性 + 时效性，约束 10③④）

profile 主表加 3 列（见 §12 migration）：

| 列 | 类型 | 含义 |
|---|---|---|
| `veracity_score` | Float(0-1) | 真实性：主张被源支撑程度 + 源可信度，LLM 判 |
| `timeliness_score` | Float(0-1) | 时效性：data_as_of 新鲜度衰减 + LLM 判是否仍当前 |
| `data_as_of` | Date | 该实体最新源 update_time/event_time |

复用现有 `confidence`（综合 = f(veracity, source)）+ `completeness`（字段填充率）。
UI（memory `project-profile-ui-upgrade` 的完整度进度条）可扩展展示真实性/时效性。

---

## 11. 字段映射（表→表 path，核心映射声明）

> 完整映射在实现期填 `ingest_ods/domain/mappings.py`，此处给骨架。

**Org ← company_basic_info（主）+ oversea_company_info + patent.applicant + market.purchaser + policy.policy_source + industry.publishing_organization**
```
company_basic_info:
  company_id           → org_id (规范键)
  company_name         → name_cn
  company_enname       → name_en
  usc_code             → (规范键 / remark)
  category_name        → tech_domains[]
  province/region_code → addresses[]
  reg_capital_num      → budgets/规模
  pension_count        → scale
  estiblish_time       → founded_date
  business_scope       → summary(片段)
  legal_person_name    → team.top_talents[](关联 Person)
  telephone/email      → remark
```

**Person ← talent_info_cn（唯一直接源）+ science.authors + patent.features.Inventor**
```
talent_info_cn:
  full_name            → name_cn (规范键 = full_name+employer)
  education            → highest_degree / educations[]
  job_title            → current_position[]
  employer             → current_org / careers[].org
  features.mail        → (规范键 email)
  features.sex         → gender
  features.discipline  → professional_domains[]
  features.graduatedUniversity → educations[].school
science_literature:
  authors[](JSON)      → 间接抽 Person（name + 该论文→academic_outputs[]）
  features.orcid_pub   → (规范键 orcid)
  features.mail        → (规范键 email)
invention_patent_cn:
  features.Inventor    → 间接抽 Person（分号切分）+ 该专利→Person 关联
```

**Tech ← science_literature + invention_patent_cn（主）+ industry_report + strategic_policy**
```
science_literature:
  title                → tech_name_cn/en (规范键 = title+keyword)
  keyword/abstract     → tech_summary / key_points[]
  features.doi         → (规范键 doi)
  features.citation_count → 影响力指标
  features.pubdate     → academic_outputs[].publish_date
invention_patent_cn:
  title                → tech_name_cn
  ipc_type             → tech_domain[]
  features.Patent_number → (规范键 Patent_number)
  legal_status/is_authorized/filing_date → current_status / application_date
  applicant            → 关联 Org
industry_report / strategic_policy:
  title/policy_source  → tech 关联 + 时间线
```

**Project ← market_analysis_cn（主）+ key_events**
```
market_analysis_cn:
  title                → name_cn[] (规范键 = title+purchaser+region)
  purchaser            → main_orgs[] / 关联 Org
  region               → (规范键之一)
  announcement_type    → status[]
  amount               → total_budget / budgets[]
  features.budget_amount / project_contact / bid_opening_time → 预算/管理人/关键日期
  event_time           → start_date / data_as_of
key_events_cn:
  title/event_time     → 项目时间线 / histories[]
```

**关系（内容→表 path 产出，写 Neo4j）**：org-研发-tech · person-隶属-org · org-中标-project · person-参与-project · org-合作-org · tech-引用-tech · org-产出-tech。

### 11.1 关系抽取全覆盖（31 RelationType 矩阵）

> **计数更正**：早期讨论称"48 关系"是把 (主体→客体) 与 (客体→主体) 两个方向各算一遍并膨胀所致。`RelationType` 枚举实际 **31 个成员**——本设计及后续文档一律用 **31**。

实现期把"关系来源"分三路，三者合起来覆盖全部 31 种（见 §19.3 关系全覆盖矩阵与 commit `a0bee7a` / `87cc815` / `11267ea`）：

| 来源 | 覆盖 | 说明 |
|---|---|---|
| **结构化规则**（`domain/relation_rules.py`） | 5 种字段隐含关系 | 表内字段直接转边，不过 LLM：`legal_person`→ORG-EMPLOY、`employer`→PERSON-AFFILIATED-ORG、`applicant`→ORG-INVOLVE-TECH、`inventor`/`authors`→TECH-CONTRIBUTOR、`purchaser`→PROJECT-MAIN-ORG。 |
| **map_predicate（文本 LLM）** | 全 31 种（含 5 卫星对） | `_PREDICATE_MAP` 52 条覆盖全 31；同值谓词按 (主,客) 元组消歧。 |
| **staging 待补** | LLM 抽出但谓词未映射 | `map_predicate` 返回 None 的谓词落 `RelationStagingORM`，不丢，待人工/补映射。 |

详见 §19.3 全矩阵 + 4 张架构/关系图（Part D 待生成，路径见 §19.4）。

---

## 12. 数据模型变更（migration）

新 alembic 迁移（`migrations/versions/00xx_ingest_ods.py`）：

1. **`db_connections`** 表（§6.1）。
2. **profile 主表加 3 列**（tech_profile / org_profile / person_profile / project_profile）：
   `veracity_score Float DEFAULT 0`、`timeliness_score Float DEFAULT 0`、`data_as_of Date NULL`。
3. **staging 表**（按 profile_type 4 张，或单表 + `profile_type` 列）：
   ```python
   class IngestRawORM:  # ingest_raw
       id pk
       profile_type   # tech/org/person/project
       source_table   # ods_xxx
       source_id      # 源表 original_id/id
       entity_key     # 规范键候选(json)
       raw_payload    # JSONB，原行+features
       extracted_at   # datetime
       batch_id       # 关联 CollectionTask.id
       status         # pending/resolved/scored/written/error
   class RelationStagingORM:  # relation_staging
       id pk; batch_id; subject_name; subject_type
       object_name; object_type; predicate; evidence; confidence; written bool
   class IngestErrorORM:  # ingest_errors
       id pk; batch_id; source_table; source_id; stage; error_msg; created_at
   ```
4. 复用 `collection_tasks`（已有）+ `EntityChangeLogORM`（已有），不改。

---

## 13. LLM 接入（约束 6、9）

- 统一 `LLMGateway.complete(model=settings.llm.<role>, messages=, caller="ods_ingest_<stage>")`，role → `llm_provider_configs.model_role`（extraction/generation/embedding/general）。
- 抽取/消歧/评分：pydantic 结构化输出（强制 JSON，复用 `llm_filler._FillOutput` 模式 + gateway 重试）。
- 长文本：chunk + 可选 embedding RAG 检索相关段。
- 成本闸：阶段② 受 `content_mine_filter` 控制；阶段④ 仅对"低 veracity 候选 / 薄实体"重评，不全量。

---

## 14. 调度与触发（约束 3、4、5）

- **cron 定时**：复用 `data_source_configs.schedule_cron`（如 `0 2 * * *` 每日 02:00 增量）。
- **手动实时**：复用 `collector_service.trigger_collection`（HTTP 触发，立即建 task 后台跑）。
- **存量首跑**：`last_watermark=null` → 全量扫；后续 cron 自动增量（watermark 之后）。
- **粒度**：`profile_types=["all"]` 一源抽 4 类（fan-out 并行），或每类独立一源分抽。两源（云/本地）可各配独立 cron。

---

## 15. 错误处理 / 可恢复

- 单批失败：记 `ingest_errors` + CollectionTask.log，跳过继续（不阻塞整任务）。
- LLM 失败：gateway 重试 + 降级（veracity=0 待补，不丢实体）。
- 断点续：`last_id`/`last_watermark` 落 config_json，重启续。
- 大表读：流式 SSCursor + id-keyset，禁 `SELECT *` 无 LIMIT，禁 `COUNT(*)`。
- 凭据：`db_connections.password_enc` 对称加密；只读账号只读。

---

## 16. 测试策略

- **Extract**：mock Doris/mirror 连接，字段映射快照（输入行 → staging_raw）。
- **ContentMiner**：LLM mock（固定 JSON 返回），验实体+关系三元组产出 + clean_content NULL 过滤。
- **Resolver**：合成跨源同名实体（company_basic_info + patent.applicant 同公司），验合并/消歧/子表累加；LLM 消歧 mock。
- **Scorer**：LLM mock，验 veracity/timeliness/data_as_of 落库 + 低分标记复核。
- **Orchestrator**：batch 边界（最后不满批）+ 并发安全（同 profile_type 互斥）+ 断点续（kill 后 `last_id` 续跑）+ batch↔workers 关系。
- **Writer**：profile upsert + Neo4j 关系 + EntityChangeLog。
- 复用现有 `tests/test_profile_*_services.py` 模式（pytest + pytest-asyncio）。

---

## 17. 前置依赖与范围边界

**本地基础设施（in scope，配独立操作手册）：**
- 本地 Doris 集群（FE+BE，Docker，opt-in profile）搭建 + `ods_zbzx` 39 表 DDL + 云→本地数据同步。
- **本地 Doris 仅用于开发/测试**：同步一个够用的子集（结构化主表抽样 + 附件少量 clean_content），非全库镜像。**生产代码部署到云端，直接读云 Doris**（同机房快）。故本地不必镜像 company 429M / 附件 1.1TB。
- 同步方案：复用 `_load_chunked*.py` 思路，目标改本地 Doris FE（同方言，DDL `SHOW CREATE TABLE` 零转换）+ 每表样本上限（SAMPLE_CAP）。慢同步 + 断点续传（last_id state）。WAN 瓶颈（TUN 关 ~2.4MB/s）下子集几小时搞定。
- **详细搭建/同步/运维步骤见** `docs/ops/local-doris-setup-manual.md`（用户可依此手动执行）。
- **mp-mysql（旧 MySQL 镜像）已删除**：Doris 转向后对"提取读"作废，容器 + H 盘卷已清。

**范围（本设计实现）：**
- `ingest_ods` 模块（orchestrator/extractor/content_miner/resolver/scorer/writer/watermark/mappings）。
- `sql_warehouse` 适配器接入 `collector_service`。
- `db_connections` + staging + profile 主表 3 列 migration。
- 两条 DataSourceConfig（云/本地）种子配置。
- 测试。
- 本地 Doris 搭建 + 同步操作手册。

**不在范围**：前端 UI 展示 veracity/timeliness（后续小改）、具体 LLM 提示词调优（实现期迭代）、全量附件 1.1TB 同步（按需）。

---

## 18. 未决 / 后续

1. 本地 Doris 集群部署形态（单机 BE / 多 BE）与云→本地同步方案选型。
2. `content_mine_filter` 阈值（structured 填充率多少算"薄"）实现期标定。
3. name 归一化规则细节（公司后缀/别名表）。
4. 关系 predicate 词表标准化（与现有 Neo4j relation schema 对齐，见 `shared/schemas/relations.py`）。
5. LLM 成本预算与 workers/batch_size 的线上标定。

---

## 19. 实现修订记录（实现期相对本设计的偏离/修正）

> 本节记录实现 TDD 任务（feat/ingest-ods 分支）相对本设计的偏离/修正。每条：**设计怎么说 / 实现怎么做 / 为什么 / commit SHA**。所有 31 种 RelationType（非早期误传的"48"）的关系覆盖矩阵见 §19.3，§6.2/§8 已就地修正。

### 19.1 偏离项

1. **watermark 按表命名空间（C2）** — `3b1422f`
   - 设计 §6.2/§8 写单 `last_id` 键。
   - 实现用 `last_id:{table}`（如 `last_id:ods_company_basic_info`），orchestrator 读写按表取键。
   - 为什么：多表 source 共用单 `last_id` 会互覆盖，导致静默跳表（C2 修复的根因）。`last_watermark` 仍是全局（`update_time`，跨表）。

2. **watermark 与 profile 原子提交（C3）** — `3b1422f`
   - 设计 §8 原文未明确提交顺序。
   - 实现：`WatermarkStore.set` 在 `_process_batch` 内、其 `await session.commit()` **之前**调用。
   - 为什么：watermark 前进与 profile 写入同事务原子提交，崩溃不会出现 watermark 已前进但 profile 未落库（或反之）的分歧。

3. **compute_entity_id 归一 list name（C1）** — `3b1422f`
   - 设计 §11 把 `market_analysis.title → name_cn[]`（project 的 `name_cn` 是 list，经 `_one` 取首项）。
   - 实现：name-fallback 取 `name[0]` 而非整个 list。
   - 为什么：否则 PK 退化成 `name:['M1', ...]`（list 的 repr），破坏主键稳定。

4. **结构化关系物化** — `a0bee7a`
   - 设计 §7② 仅说"LLM 抽关系"（关系全走内容→表路径）。
   - 实现加 `domain/relation_rules.py`，把表内字段隐含的关系直接转边，不过 LLM：
     - `legal_person` → ORG-EMPLOY
     - `employer` → PERSON-AFFILIATED-ORG
     - `applicant` → ORG-INVOLVE-TECH
     - `inventor` + `authors` → TECH-CONTRIBUTOR
     - `purchaser` → PROJECT-MAIN-ORG
   - 为什么：这些关系在结构化列里就是确定事实，过 LLM 既慢又会丢。

5. **name→PK 解析 + profile Neo4j 节点 + 卫星 ensure** — `a0bee7a` `f4c4da3`
   - 设计未提 id 对齐。
   - 实现加：
     - `NameIndex`——批内 (type,name)→PK 解析；未命中的留 `name:` 前缀卫星节点（`NAME_SATELLITE_PREFIX="name:"` 提常量）。
     - `Writer.upsert_profile_node`——profile 也写 Neo4j 节点，`entity_id=PK`。
     - `write_relations` 前 ensure 卫星节点。
   - 为什么：Neo4j `upsert_relation` 的 MATCH 基在两端节点不存在时静默丢边；先 ensure 卫星节点保证边落地。卫星前缀让后续重跑/解析命中后能升级为真实 PK。

6. **content_miner 未映射谓词落 relation_staging** — `11267ea`
   - 设计 §7② 说 LLM 抽关系直接产出。
   - 实现把 `map_predicate` 返回 None 的谓词落 `RelationStagingORM`（不丢，待人工/补映射）；`mine()` 返回 3-tuple。
   - 为什么：未映射谓词直接丢等于丢关系数据；先落 staging 可追溯、可补。

7. **EntityType 扩 5 卫星类（全 31 关系进图）** — `9bcfee4` `973571c` `5702f95`
   - 设计 RelationType 覆盖卫星实体，但 EntityType 仅 4 类（tech/org/person/project）。
   - 实现加 STRATEGY / EVENT / ENTERPRISE / CONTRACT / PACKAGE 共 5 卫星类，**值用 ASCII**（`Strategy`/`Event`/...）。
   - 为什么：`.value` 是 load-bearing 标识符——`id_generator`、PG `entity_type` 列、ES 索引名都用它；中文字面会破坏。Neo4j label 图（§A2）+ 前端 `TYPE_META`（§A4/A5）同步补。

8. **`_PREDICATE_MAP` 全覆盖** — `87cc815`
   - 设计枚举 31 种 RelationType。
   - 实现 `_PREDICATE_MAP` 52 条覆盖全 31（含卫星对）；同值谓词按 (主,客) 元组消歧。parametrize 全枚举覆盖断言钉死。
   - 为什么：否则新加 RelationType 时 `map_predicate` 静默落空，关系进不了图。

9. **migration 0004** — `1c19784`
   - `project_profile.project_no` 去 UNIQUE。
   - `start_date` nullable。
   - 为什么：ODS 批量灌库第 2 行 `project_no` 重复（同采购方多标段）即 IntegrityError；`start_date` 在早期/未公告项目为空。

10. **已知局限**：`NameIndex` 是批内解析——跨批/跨表 name 不解析 → 留 `name:` 卫星。需持久化 (type,name)→PK store 才能跨批消歧，列入后续。

### 19.2 计数更正

> 早期讨论与 task 注释（如 "#22 全 48"）把关系数算成 **48**——那是把 (主体→客体) 与 (客体→主体) 两个方向各算一遍并按 pair 膨胀。`RelationType` 枚举实际 **31 个成员**。本设计、§11.1、§19.4 一律用 **31**；后续遇到"48"应理解为该计数错误。

### 19.3 关系抽取全覆盖矩阵（31 RelationType）

按 (主体→客体) pair 分组，标注覆盖来源（**结构化规则**=relation_rules / **map_predicate**=文本 LLM / **staging 待补**=未映射谓词落 RelationStaging）。三路合起来覆盖全 31；同 pair 多谓词由 `_PREDICATE_MAP` 按 (主,客) 元组消歧（见 §19.1.8）。

| # | RelationType | 主体→客体 | 结构化规则 | map_predicate | staging |
|---|---|---|:-:|:-:|:-:|
| 1 | ORG-INVOLVE-TECH | Org → Tech | ✅ applicant | ✅ | ✅ |
| 2 | ORG-EMPLOY | Org → Person | ✅ legal_person | ✅ | ✅ |
| 3 | PERSON-AFFILIATED-ORG | Person → Org | ✅ employer | ✅ | ✅ |
| 4 | TECH-CONTRIBUTOR | Tech → Person | ✅ inventor/authors | ✅ | ✅ |
| 5 | PROJECT-MAIN-ORG | Project → Org | ✅ purchaser | ✅ | ✅ |
| 6 | ORG-PRODUCE-TECH | Org → Tech | — | ✅ | ✅ |
| 7 | TECH-REFERENCE-TECH | Tech → Tech | — | ✅ | ✅ |
| 8 | ORG-COLLABORATE-ORG | Org → Org | — | ✅ | ✅ |
| 9 | PERSON-PARTICIPATE-PROJECT | Person → Project | — | ✅ | ✅ |
| 10 | ORG-BID-PROJECT | Org → Project | — | ✅ | ✅ |
| 11 | PROJECT-INVOLVE-TECH | Project → Tech | — | ✅ | ✅ |
| 12 | TECH-USED-BY-PROJECT | Tech → Project | — | ✅ | ✅ |
| 13 | ORG-FUND-TECH | Org → Tech | — | ✅ | ✅ |
| 14 | PERSON-AUTHOR-TECH | Person → Tech | — | ✅ | ✅ |
| 15 | PERSON-INVENT-TECH | Person → Tech | — | ✅ | ✅ |
| 16 | ORG-SUBSIDIARY-ORG | Org → Org | — | ✅ | ✅ |
| 17 | ORG-PARTNER-ORG | Org → Org | — | ✅ | ✅ |
| 18 | PROJECT-FUNDER-ORG | Project → Org | — | ✅ | ✅ |
| 19 | PROJECT-CONTRACTOR-ORG | Project → Org | — | ✅ | ✅ |
| 20 | TECH-OWNED-BY-ORG | Tech → Org | — | ✅ | ✅ |
| 21 | PROJECT-BELONG-STRATEGY | Project → Strategy | — | ✅ | ✅ |
| 22 | ORG-RESPOND-EVENT | Org → Event | — | ✅ | ✅ |
| 23 | EVENT-IMPACT-PROJECT | Event → Project | — | ✅ | ✅ |
| 24 | EVENT-IMPACT-TECH | Event → Tech | — | ✅ | ✅ |
| 25 | ENTERPRISE-INVEST-PROJECT | Enterprise → Project | — | ✅ | ✅ |
| 26 | CONTRACT-RELATE-PROJECT | Contract → Project | — | ✅ | ✅ |
| 27 | PACKAGE-CONTAIN-PROJECT | Package → Project | — | ✅ | ✅ |
| 28 | ORG-LOCATE-EVENT | Org → Event | — | ✅ | ✅ |
| 29 | TECH-BELONG-PACKAGE | Tech → Package | — | ✅ | ✅ |
| 30 | PERSON-LEAD-PROJECT | Person → Project | — | ✅ | ✅ |
| 31 | STRATEGY-DRIVE-TECH | Strategy → Tech | — | ✅ | ✅ |

> 上表 #16-31 涉及 Strategy/Event/Enterprise/Contract/Package 等 5 卫星 EntityType（见 §19.1.7）；具体 RelationType 命名以实现期 `shared/schemas/relations.py` 枚举为准（本表给出方向性占位，重在展示三路覆盖——结构化规则负责 5 种字段隐含关系、map_predicate 覆盖全 31 含卫星对、未映射谓词进 staging）。

### 19.4 架构与关系图（Part D 待生成）

实现期 4 张图（Part D，由 fireworks-tech-graph 生成）：

- `docs/diagrams/ods-arch.{svg,png}` — ODS 抽取流水线总体架构（5 阶段 + 两路径 LLM + staging）。
- `docs/diagrams/ods-relations.{svg,png}` — 31 RelationType 关系图谱（主体/客体/卫星 EntityType，标注三路来源）。
- `docs/diagrams/ods-watermark.{svg,png}` — 批次编排 + watermark 原子提交 + per-table 命名空间（C2/C3）。
- `docs/diagrams/ods-name-pk.{svg,png}` — NameIndex (type,name)→PK 解析 + 卫星 ensure + profile Neo4j 节点。

> 文件尚未创建（forward link）；Part D 完成后路径不变，§11.1 的图链与此对齐。
