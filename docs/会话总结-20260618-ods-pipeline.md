# 会话总结 · ODS→四类画像抽取管线实现（2026-06-18）

## 目标
在 `feat/ingest-ods` 分支用 subagent-driven-development 执行 15 任务 TDD 计划，构建 `metaprofile/ingest_ods/`——从 ODS Doris 抽取 Tech/Project/Org/Person 画像 + 关系的批处理管线。执行中按整体审查 + 用户追问补齐关系抽取全覆盖、文档回写、4 张图。最终合并 main。

## 产出

### 管线（T1-T15，`metaprofile/ingest_ods/`）
- **domain/**：`orm_models`（DBConnectionORM/IngestRawORM/RelationStagingORM/IngestErrorORM）、`mappings`（5 表→画像字段映射 + `_feat`/`_resolve`/`_build_key`）、`relation_rules`（表字段→关系边规则）。
- **services/**：`security`（Fernet 密码）、`connections`（DSN 解析）、`watermark`（last_id/last_watermark）、`extractor`（id-keyset 抽取）、`resolver`（强键归并 + LLM 消歧）、`scorer`（真实性/时效性 LLM）、`writer`（profile upsert + 评分 + 变更日志 + 关系 + profile Neo4j 节点）、`content_miner`（附件 LLM 抽实体/关系）、`orchestrator`（批次 + 并发 + 互斥 + 续传）、`name_index`（批内 name→PK 解析）。
- **llm/prompts**：pydantic schema + `_PREDICATE_MAP`（52 条覆盖全 31 RelationType）+ `map_predicate`。
- **collectors/sql_warehouse**：`source_type="sql_warehouse"` 适配器 + collector_service 接线 + 内容挖掘。
- **migrations**：0003（ingest 表 + 4 画像评分列）、0004（project_no 去 UNIQUE / start_date nullable）。
- **scripts/seed_ods_datasources**：幂等种子（db_connections + data_source_configs）。

### 整体审查修的 3 Critical（commit 3b1422f）
- **C1** `compute_entity_id` 归一 list name（project `name_cn=['M1']`→`'name:M1'` 非 list repr，否则 PK 破坏）。
- **C2** watermark `last_id:{table}` 按表命名空间（多表 source 不互覆盖/跳过）。
- **C3** watermark 与 profile 原子提交（`set` 在 `_process_batch` commit 前，崩溃不分歧）。

### 关系抽取全覆盖
- `_PREDICATE_MAP` 全 **31** RelationType（含卫星实体；纠正早前"48"误数——章节注释按方向数多算）。
- 结构化 `relation_rules`：legal_person→ORG-EMPLOY / employer→PERSON-AFFILIATED-ORG / applicant→ORG-INVOLVE-TECH / inventor+authors→TECH-CONTRIBUTOR / purchaser→PROJECT-MAIN-ORG。
- content_miner 未映射谓词落 `RelationStagingORM`（不丢，待人工/补映射）。
- `EntityType` 扩 5 卫星类（STRATEGY/EVENT/ENTERPRISE/CONTRACT/PACKAGE，值 ASCII——`.value` 是 load-bearing 标识符：id_generator/PG entity_type 列/ES 索引名）。
- name→PK 解析（`NameIndex`）+ profile Neo4j 节点（`upsert_profile_node`，entity_id=PK）+ 卫星节点写前 ensure（修 Neo4j `upsert_relation` MATCH 基静默丢边，commit f4c4da3）。

### 本地 Doris 基础设施（commit 0e4ee4b 实测修 3 bug）
- 镜像 tag：`doris-2.1.11-fe/be` → `fe-2.1.11`/`be-2.1.11`（官方 apache/doris 命名）。
- `FE_SERVERS`：`name:ip:port:port:port` → `name:ip:port`（entrypoint 仅认单端口）。
- BE 加 `FE_SERVERS`（集群发现模式 → BE 自动注册，免手动 ADD BACKEND）。
- `_doris_ddl_sync` regex 覆盖 `dynamic_partition.replication_allocation`（34 表不再 SKIP）。
- 38/39 表 DDL 应用；loader 改本地 Doris（DELETE→INSERT 幂等 + UNIQUE-KEY MoW upsert + SAMPLE_CAP），后台灌数（science/strategic/small 表完成/in-progress；big3 company/market/patent + 附件未灌）。

### 设计文档 + 图
- 设计文档（`docs/superpowers/specs/2026-06-17-ods-profile-extraction-design.md`）：§6.2/§8 修正（per-table watermark、原子提交、互斥）；§19 实现修订记录（10 条带 commit SHA）；关系全覆盖矩阵（31）；纠正 48→31。
- 4 张图（`docs/diagrams/ods-{arch,flow,relation-matrix,dataflow}.{svg,png}`，fireworks-tech-graph + Playwright CJK 保真）。

## 质量
- **ingest_ods 100 测试 / 全套 414 passed，0 回归**。
- 每任务两阶段审查（spec compliance + code quality），审查发现的 bug 全修 + 补回归测试钉死。
- 前端 TYPE_META 补卫星类，`npm run build` 过。

## 已知局限（后续）
- `NameIndex` 批内——跨批/跨表 name 不解析→留 `name:` 卫星（需持久 (type,name)→PK store）。
- big3 表（company 429M / market 36M / patent 29M）+ 附件表未灌本地 Doris（loader 后台跑小/中表，大表待单独启）。
- migration 0004 downgrade 重建 UNIQUE 约束名硬编码（生产单向部署无碍，alembic downgrade 复现性略损）。

## 流程复盘
- subagent-driven（implementer→spec 审→code-quality 审→commit）质量高：整体审查抓出 3 个单任务审查看不到的跨任务 Critical（C1/C2/C3）+ 关系卫星 MATCH 静默丢边。
- 后台并行灌数（Doris loader）与管线开发独立，节省墙钟。
- 教训：EntityType.value 是 load-bearing 标识符，扩枚举值须与既有 ASCII 风格一致（我计划误开中文值，审查期发现即改）。
