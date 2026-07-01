# 云上只读轻量部署设计(单 ECS + Docker,去 Doris)

- 日期:2026-07-01
- 状态:draft,待用户评审
- 决策来源:本会话 brainstorming 逐项确认(阿里云 / 单 ECS / 去 Doris / 纯只读 / PG 预导入数据)

## 1. 目标

在阿里云单台 ECS 上跑一个**纯只读** MetaProfile:

- 去掉 Doris(14G ODS 引擎)+ 所有 LLM/采集任务
- 数据预导入(本地造好的数据 → 云)
- profile 读 API + UI 可用
- 一条命令(terraform)+ user-data 自动起全栈

**非目标**:实时采集、enrichment、tech_concept 抽取、对外多租户、高可用。

## 2. 背景与约束

本地栈(14 服务):postgres、neo4j、redis、rabbitmq、elasticsearch、litellm、doris-fe、doris-be、backend、backend-worker、frontend + migrate/seed。

- postgres 才 1.9MB(配置 + 少量 typed ORM profile 数据)
- 大数据(big3:company 13.27M / market 7.5M / patent 6M / science 5.58M)**全在 Doris H: 14G bind-mount**
- 云版**不迁 Doris**,只迁 postgres + neo4j 的预造数据

grep 确认的依赖边界:
- redis → profile stats cache(backend 运行期用,**留**)
- elasticsearch → 只 `foundation/enrichment/rag_retriever` + `foundation/storage/es_repo` 用(LLM 任务,云版不跑 → **去**)
- `backend/main.py` 启动只 import postgres;ES/neo4j/redis 全 lazy(get_xxx 调用时才连)→ 去容器不破坏启动

## 3. 栈(单 ECS docker-compose)

| 组件 | 去/留 | 说明 |
|------|------|------|
| postgres | ✅ 留 | 容器,ESSD 数据卷,预导入数据 |
| neo4j | ✅ 留 | 容器,ESSD 数据卷,关系图谱 |
| redis | ✅ 留 | 容器,profile stats cache |
| backend | ✅ 留 | 容器,profile 读 API |
| frontend | ✅ 留 | 容器,UI |
| **doris-fe / doris-be** | ❌ 去 | 熔断 |
| **litellm** | ❌ 去 | 不跑 LLM |
| **backend-worker + beat** | ❌ 去 | 不跑 celery 任务 |
| **rabbitmq** | ❌ 去 | 无 worker 无需 broker |
| **elasticsearch** | ❌ 去 | 只 enrichment 用,熔断 |

ECS 规格:neo4j 吃内存,起步 **8C 16G**,ESSD PL1 数据盘 **200G**(postgres + neo4j 数据)。实测后调。

## 4. 熔断机制(env flag)

环境变量:
```
MODE=readonly
ODS_ENABLED=false
```

实现:**不删码**(本地全量模式 `MODE=full` 仍可用)。受影响路由的 handler 首行检查 flag,未启用则返回:
```json
HTTP 503 {"detail": "disabled in readonly mode"}
```
frontend 读同 flag,**隐藏**对应菜单入口(不调 disabled 端点)。

熔断清单(具体模块):

| 模块 | 路径 | 原因 |
|------|------|------|
| ingest_ods 全域 | `ingest_ods/services/{orchestrator,extractor}.py`、`collectors/sql_warehouse.py`、`domain/orm_models.py` | 读 ODS Doris |
| 采集 cron | `shared/worker/collection_tasks.py`、`shared/scheduler/poller.py`(collection dispatch 分支) | 采集→Doris |
| 新技术发现 | `shared/worker/newtech_tasks.py`、`new_tech_discovery/api/routes_*.py`、`services/corpus_loader.py` | 读 ODS |
| ODS 数据源 CRUD | `settings_api/api/routes_db_connections.py`、`services/collector_service.py` | 连 Doris |
| enrichment/rag | `foundation/enrichment/*`(rag_retriever)、`foundation/storage/es_repo.py` | 走 ES+LLM |

**保留**:profile 读层全部(org/person/project/tech `routes_query`/`routes_relation`/`routes_enrichment` 的 GET + `*_stats_service`),跨画像跳转,/explore。

> 备注:`routes_enrichment` 名字含 enrich 但属 profile 层(展示已 enrich 结果的 GET),不调 LLM → 保留。需在实现时逐 endpoint 核对(写 GET vs POST 触发)。

## 5. 数据预导入

| 数据 | 导出(本地) | 中转 | 导入(云 ECS) |
|------|------------|------|--------------|
| PG typed 表 + 配置 | `pg_dump --data-only`(指定 schema/表;配置表 `db_connections`/`llm_provider_configs` 视是否留历史) | OSS HTTPS 上传 | user-data `pg_restore` 进 postgres 容器 |
| Neo4j | `neo4j-admin database dump neo4j` | OSS | user-data `neo4j-admin load` |

OSS 中转:出口段(本地→OSS)走**公网 HTTPS**(本地无专线,不可避);云内段(ECS→OSS)走 **VPC 内网 endpoint**(免费 + 快)。

> 若本地 PG 数据稀疏(1.9MB),可改用造数脚本(memory `project_data_write_path` 记有造数脚本结论)在云 postgres 容器直接重跑补数据。二选一在实现时定。

## 6. 一键 IaC

**Terraform**(alicloud provider):

- VPC + vSwitch + 安全组(放行 80/443/22)
- 1 台 ECS(指定规格,ESSD 数据盘 200G,公网 EIP)
- OSS bucket(放 dump + readonly compose 文件)
- user-data 脚本:
  1. 装 docker + docker compose
  2. 从 OSS(内网 endpoint)拉 readonly compose + dump
  3. `docker compose up -d` 起 postgres/neo4j/redis(等健康)
  4. `pg_restore` + `neo4j-admin load` 灌数据
  5. `docker compose up -d` 起 backend + frontend

**一键命令**:`terraform apply -var-file=cloud.tfvars`(基建 + 应用全自动)。

**密钥**:
- OSS AK/SK + ECS key pair → Terraform 变量(不入仓,`.tfvars` gitignore)
- 无 glm key(不跑 LLM)
- postgres/neo4j 密码 → user-data 首次生成 + 写 ESSD(或走 KMS,后续优化)

## 7. 网络拓扑

```
本地 ──(公网 HTTPS 上传)──> OSS bucket
                                │ (VPC 内网拉)
                                ▼
        ┌─────────────── 单 ECS (docker) ───────────────┐
        │  frontend:80  backend:8000  (对外:EIP/SLB)    │
        │    │              │                           │
        │    └── redis ── backend (stats cache)         │
        │    └── neo4j:7687 ── backend (关系)            │
        │    └── postgres:5432 ── backend (profile 读)   │
        └────────────────────────────────────────────────┘
出公网:无(不调 glm)
```

## 8. 验收标准

- [ ] `terraform apply` 起单 ECS + OSS 成功,无手动介入
- [ ] user-data 自动:docker 起 5 容器(postgres/neo4j/redis/backend/frontend)全 healthy
- [ ] 数据预导入:profile API 返回真实数据(`/api/profile/org/...` 等非空)
- [ ] 熔断:`collection_tasks` / `db_connections` / `new_tech` / `enrichment` POST 端点返回 503;UI 菜单隐藏对应入口
- [ ] 本地全量模式(`MODE=full`)测试仍绿,flag 不影响现有行为
- [ ] frontend 经 EIP 可访问,profile 页可浏览 + 跨画像跳转 + /explore 可用

## 9. 风险与已知

- **postgres 自管无高可用/自动备份** → 需定时 `pg_dump` 到 OSS(cron 或 ESSD 快照)。生产长期建议后续升 RDS。
- **neo4j 单点** → ESSD 数据盘快照备份。
- **单 ECS 单点** → 纯只读可接受;若要 HA 后续升多机/ACK。
- **熔断 flag 是新代码** → 需开发:env 读取 + 路由 guard(依赖注入或中间件)+ 前端 flag。这是主要开发量。
- **ECS 规格** → neo4j 内存吃紧,实测后调(16G 不够升 32G)。
- **user-data 失败排查** → cloud-init 日志(`/var/log/cloud-init-output.log`)。
- **readonly compose 文件** → 需从现有 `deploy/docker-compose.yml` 派生(去 doris/litellm/worker/rabbitmq/es,加 env flag)。新建 `deploy/docker-compose.readonly.yml`。

## 10. 实现拆分(预告,详细 plan 由 writing-plans 出)

1. readonly compose 文件派生 + env flag 接入
2. 熔断 guard 机制(env 读 + 路由 + 前端)
3. 数据导出脚本(pg_dump + neo4j dump → 打包)
4. user-data 部署脚本(docker + restore + up)
5. Terraform 模板(VPC/ECS/OSS/安全组)
6. 验收脚本(端到端 health + API 抽查)
