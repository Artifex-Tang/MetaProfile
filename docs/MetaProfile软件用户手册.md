# MetaProfile 软件用户手册

> 本手册基于《软件用户手册》模板生成，复用模板封面、自动目录（TOC）、页眉页脚与样式；章节标题由 Word 自动编号。

## 范围

### 标识

本手册适用于 MetaProfile 产业技术情报系统 V1.0。系统面向技术、项目、机构、人员四类实体画像，提供数据采集、治理、检索、关联分析，以及前沿技术扫描、弱信号发现、选题生成等情报分析能力。

### 系统概述

系统由前端（React + nginx）与单一复合后端（FastAPI）组成，采用 Docker Compose 编排，默认启动全部服务。

![图1 系统架构](docs/diagrams/architecture.png)

- 复合后端 `backend`（端口 8000）：单一 FastAPI 应用，聚合画像层（技术 / 项目 / 机构 / 人员）、分析层（扫描监测 / 新技术发现 / 选题服务）与配置层的全部路由。
- 前端 `frontend`（端口 80）：nginx 监听 80，按前缀 `/api-tech`、`/api-project`、`/api-org`、`/api-person`、`/api-scan`、`/api-discovery`、`/api-topic`、`/api-settings` 反向代理至 `backend:8000`，前缀剥离后落到后端 `/api/v1` 路由空间。
- 基础设施：PostgreSQL（5432，主库）、Elasticsearch（9200，全文检索）、Redis（6379，缓存）。
- 增强组件（默认随主栈启动）：Neo4j（7474/7687，实体关系图谱）、RabbitMQ（5672/15672，扫描/采集/选题等异步任务）、LiteLLM（4000，大模型统一代理）。
- 一次性任务：`migrate`（数据库迁移）、`seed`（示例数据灌入），成功后退出，不计入常驻健康容器。
- 前端入口：左侧导航含总览、技术画像、项目画像、机构画像、人员画像、扫描监测、新技术发现、选题服务、系统配置共九个功能页面。

### 文档概述

本手册第 1 章界定范围与典型业务场景；第 2 章列出引用文件；第 3 章给出运行资源与人员要求；第 4 章说明交付、安装与升级；第 5 章为操作使用指导，逐一描述九个功能页面的可达交互，含关系图谱跨画像跳转；第 6 章为附录。

### 典型业务场景

系统围绕"采集—画像—发现—研判—选题"的情报闭环组织功能。

![图2 业务闭环](docs/diagrams/flow.png)

典型场景与涉及页面如下：

| 场景 | 业务目标 | 主要页面与交互 |
|---|---|---|
| 竞争对手技术布局追踪 | 掌握某领域前沿技术及其研发主体 | 扫描监测（触发扫描）→ 前沿技术详情（六维评分）→ 技术画像 → 关系图谱跨画像跳转至关联机构 / 人员 |
| 新兴技术弱信号发现 | 在专利/文献突现前识别潜在方向 | 新技术发现（触发发现扫描）→ 弱信号列表 → 信号关联网络图 → 确认后纳入技术画像 |
| 人物与机构画像研判 | 还原关键人物履历、机构沿革与合作网络 | 人员 / 机构画像（搜索、详情）→ 关系图谱 → 跨画像链式跳转（人员↔机构↔项目↔技术） |
| 选题辅助决策 | 基于多维评分生成并评审研究选题 | 选题服务（生成选题、评分详情、评审反馈）→ 关联技术 / 机构 / 项目 |
| 自动化数据采集入库 | 定时从外部源拉取并结构化入库 | 系统配置（数据源配置、定时 cron、立即采集）→ 采集任务（监控、日志）→ 画像自动更新 |

## 引用文件

| 文件 | 用途 |
|---|---|
| `deploy/docker-compose.yml` | 服务编排定义 |
| `deploy/.env.example` | 环境变量模板 |
| `deploy/litellm.yaml` | 大模型代理配置 |
| `deploy/pg_init/01_init.sql` | PostgreSQL 初始化脚本 |
| `frontend/nginx.conf` | 前端反向代理配置 |
| `使用手册.md` | 部署与运维速查 |
| `http://localhost:8000/docs` | 复合后端 Swagger 接口文档 |

## 要求

### 资源应用

运行所需资源由 Docker 容器统一封装，宿主机仅需 Docker 环境。

### 硬件要求

| 项 | 最低 | 建议 |
|---|---|---|
| CPU | 4 核 | 8 核 |
| 内存 | 8 GB | 12 GB（Elasticsearch ~2 GB，Neo4j ~2 GB） |
| 磁盘 | 10 GB | 20 GB（镜像 + 数据卷） |
| 端口 | 80、5432、6379、9200、7474、7687、5672、15672、4000、8000 空闲 | 同左 |

### 软件要求

| 依赖 | 最低版本 | 说明 |
|---|---|---|
| Docker Engine | 24.x | 含容器运行时 |
| Docker Compose | v2.x | 服务编排 |

验证：

```bash
docker version
docker compose version
```

### 培训与人员

| 角色 | 职责 | 建议培训内容 |
|---|---|---|
| 部署运维人员 | 安装、启动、升级、备份、排障 | Docker Compose、PostgreSQL、Elasticsearch 基础 |
| 业务分析人员 | 画像检索、关系分析、选题评审 | 四类画像字段、关系图谱跨画像跳转 |
| 情报研究人员 | 数据导入、报告输出 | 批量导入 JSON 格式、采集任务监控 |

### 后勤保障与组织

系统部署于单机或集群，运维由部署单位负责。数据备份与恢复流程见"数据备份与恢复"一节。

### 试验与评判

安装完成后按"安装验证"逐项确认；升级后按"升级验证"确认；功能验证按"操作过程"各功能页操作执行。

## 交付与安装

### 对首次使用的用户

首次使用者应熟悉第 5 章操作流程，确认硬件与软件要求（硬件要求、软件要求）满足，按"安装"完成首次部署。

### 安装

#### 安装前准备

确认 Docker 已就绪、所需端口未被占用：

```bash
docker compose version
```

#### 安装过程

进入部署目录并配置环境变量：

```bash
cd MetaProfile/deploy
cp .env.example .env
```

启用大模型功能（可选）：编辑 `.env`，填入 LiteLLM 主密钥与各厂商 API Key：

```env
LLM_PROXY_API_KEY=sk-your-master-key
QWEN_API_KEY=sk-xxxx
DEEPSEEK_API_KEY=sk-xxxx
```

部署拓扑如图所示。

![图3 部署拓扑](docs/diagrams/deployment.png)

构建并启动：

```bash
docker compose up -d --build
```

首次构建约需 5–10 分钟（视网络）。`migrate`、`seed` 为一次性任务，执行成功后退出；Elasticsearch 启动约需 60 秒，其他服务等待其就绪后启动。

#### 安装验证

```bash
docker compose ps
```

常驻容器应显示 `(healthy)`：postgres、elasticsearch、redis、neo4j、rabbitmq、litellm、backend、frontend 共 8 个；`migrate`、`seed` 显示 `exited (0)` 属正常。浏览器访问 http://localhost 能看到总览仪表盘即安装成功。

![图4 安装验证——总览仪表盘](docs/manual_shots/01_dashboard.png)

### 升级

#### 升级前准备

升级前务必完成数据备份（见"数据备份与恢复"），并记录当前版本号与镜像 ID，便于回滚。确认新版本镜像或源码已就绪，所需端口与 3.2、3.3 资源要求仍满足。

#### 升级过程

拉取新镜像或更新源码后，滚动重建服务：

```bash
cd MetaProfile/deploy
git pull                       # 源码升级时
docker compose pull            # 镜像升级时
docker compose up -d --build   # 重建变更的容器，数据卷保留
```

如新版本含数据库结构变更，`migrate` 一次性任务会自动执行；可在日志中确认：

```bash
docker compose logs migrate
```

#### 升级验证

```bash
docker compose ps              # 常驻容器均 (healthy)
docker compose logs --tail=20 migrate
```

浏览器访问 http://localhost 确认总览仪表盘与各画像页加载正常，并抽检四类画像搜索与关系图谱。若升级异常，按"诊断故障处理"查日志；必要时按备份回滚：

```bash
docker compose down
# 恢复 PostgreSQL 备份后
docker compose up -d
```

### 培训

参照"培训与人员"角色与培训内容组织培训，建议结合"操作过程"各功能页与"典型业务场景"实操。

## 操作使用指导

### 启动

日常启动（已构建过）：

```bash
cd MetaProfile/deploy
docker compose up -d
```

启动后访问 http://localhost。

### 约束

- 数据卷删除（`docker compose down -v`）不可恢复，执行前确认已备份。
- Elasticsearch 索引随数据写入自动创建；未导入数据时搜索无结果。
- 大模型相关功能（LLM 抽取/补全、智能生成）需在系统配置页接入模型或填写 `.env` API Key 后生效。

### 操作过程

#### 总览

![图5 总览仪表盘](docs/manual_shots/01_dashboard.png)

- 顶部四张统计卡片：技术、项目、机构、人员画像总数；点击卡片跳转对应画像页。
- 前沿技术 Top 5 表（按融合评分排序）：展示技术名称、领域、融合评分、TRL、状态；点击行跳转扫描监测。
- 最新告警表：展示技术、告警类型、级别、消息、时间；点击行跳转扫描监测。

#### 技术画像

![图6 技术画像列表](docs/manual_shots/02_tech_list.png)

- 搜索：搜索框输入关键词，回车触发全文检索。
- 新建：点击"新建"，填写中文名、英文名、领域、状态、摘要后提交。
- 批量导入：点击"批量导入"选择 JSON 文件。格式示例：

```json
[
  {
    "tech_name_cn": "量子纠错",
    "tech_name_en": "Quantum Error Correction",
    "tech_domain": ["量子计算", "基础研究"],
    "current_status": "emerging",
    "tech_summary": "利用冗余量子比特纠正退相干误差的技术。"
  }
]
```

- 查看详情：点击"详情"或双击行打开抽屉，含基本信息、里程碑、科研成果（经费/学术成果/科研实验）、统计图表（领域分布柱状图、完整度饼图）、关联图谱。

![图7 技术画像详情抽屉](docs/manual_shots/10_tech_detail_drawer.png)

- LLM 补全：详情抽屉标题区"LLM 补全"按钮，提交字段补全任务。

#### 项目画像

![图8 项目画像列表](docs/manual_shots/03_project_list.png)

搜索、批量导入操作同技术画像。详情抽屉含基本信息（名称、领域、起止时间、主管/承研机构、负责人、研究人员、预算、研究目标、关键词）、研究内容、发展历程、预算明细、项目成果、关联图谱。

#### 机构画像

![图9 机构画像列表](docs/manual_shots/04_org_list.png)

搜索、批量导入操作同技术画像。详情抽屉含基本信息（名称、国家、成立时间、类型、规模、技术领域、职能）、发展沿革、科研队伍（规模、人才类型、顶尖人才）、科研设施、主要成果、荣誉奖励、关联图谱。

#### 人员画像

![图10 人员画像列表](docs/manual_shots/05_person_list.png)

搜索、批量导入操作同技术画像。详情抽屉含基本信息（姓名、国籍、职务、专业领域、学历、类别）、工作经历、教育经历、学术成果、技术关注、关联图谱。

#### 关系图谱与跨画像跳转

技术、项目、机构、人员四类画像的详情抽屉均含"关联图谱"页，以力导向图展示当前实体与相邻实体的关联，节点按实体类型着色（技术蓝 / 项目紫 / 机构绿 / 人员橙）。

![图11 关联图谱](docs/manual_shots/11_tech_relation_graph.png)

- 查看关联：图谱中心为当前实体，周围为关联实体，边标注关系类型（隶属、合作、涉及、贡献者等）。支持拖拽节点、缩放画布、悬停高亮可跳节点。
- 跨画像跳转：点击任一可跳节点，直接跳转到该实体对应类型的画像详情页，顶部显示来源面包屑（来源实体 —经 关系— 当前实体）。点击面包屑中的来源实体可返回来源。

![图12 跨画像跳转](docs/manual_shots/12_cross_profile_jump.png)

- 可跳范围：仅技术、项目、机构、人员四类节点可跳；企业、战略等扩展类型节点不可跳（保持普通指针）。
- 链式分析：在目标画像的关联图谱中可继续点击节点跳转，形成多跳跨画像分析链路，任意节点可经面包屑返回来源。
- 刷新与分享：跳转后刷新页面，详情正常加载，面包屑退化为仅显示来源实体（关系信息不保留）；直接分享详情链接可打开目标画像，但不携带来源上下文。

#### 扫描监测

![图13 扫描监测](docs/manual_shots/06_scan.png)

- 触发扫描：选择分析时间范围（起止日期）、可选填技术领域（支持多选，预设人工智能、量子计算、生物技术、新能源、先进制造、新材料），点击"开始扫描"。扫描为异步任务，约 2 秒后列表刷新。
- 前沿技术列表：展示技术名称、领域、融合评分、TRL、状态（已验证 / 待验证 / 已排除）。点击"详情"抽屉展示六维评分（融合、爆发、专利、引用、投资、政策）、分析周期、TRL、LLM 验证结果与判定。

![图14 前沿技术详情](docs/manual_shots/14_scan_detail.png)

- 告警列表：展示技术、告警类型（突现 / TRL 升级 / 机构布局）、级别（严重 / 警告 / 信息）、消息、时间。点击"查看"弹出告警详情。

#### 新技术发现

![图15 新技术发现](docs/manual_shots/07_discovery.png)

- 触发发现扫描：点击"触发发现扫描"，系统自动检测弱信号，约 2 秒后列表刷新。
- 弱信号列表：展示关键词、强度、新颖度、一致性、领域、状态（活跃等）。
- 信号关联网络：点击"网络图"，抽屉以力导向图展示该信号关联的技术、机构、人员节点（按类型着色：技术蓝 / 机构绿 / 人员橙 / 信号紫），边标注类型，线宽随权重变化，可交互拖拽。

#### 选题服务

![图16 选题服务](docs/manual_shots/08_topics.png)

- 生成选题：点击"生成选题"，填写数量（1–100）、可选分析周期，提交后约 3 秒列表刷新。
- 状态筛选：下拉框筛选待处理 / 已采纳 / 已拒绝 / 已修订。
- 选题列表：展示标题、周期、综合评分、状态、热度。点击标题或"详情"打开抽屉。

![图17 选题详情抽屉](docs/manual_shots/13_topic_detail.png)

- 详情抽屉：基本信息（ID、周期、状态、摘要）；评分详情（热度、政策、影响力、去重、LLM 五维进度条，及新颖度、重要性、可行性、表达、综合评分）；评审依据；关联技术 / 机构 / 项目。
- 提交反馈：抽屉右上角"提交反馈"：选择评审结论（接受 / 拒绝 / 修改）、评分（1–10）、评审意见。

#### 系统配置

系统配置含三个标签页。

![图18 系统配置——大模型配置](docs/manual_shots/09_settings.png)

- 大模型配置：新增 / 编辑 / 删除 LLM 接入（支持 OpenAI、Azure、Anthropic、Gemini、DashScope、DeepSeek、智谱、Kimi、百川、MiniMax、零一万物、Qwen、Ollama、vLLM、Together、Mistral、Cohere、Bedrock、自定义等厂商）；配置模型角色（通用 / 抽取 / 生成 / 向量化）、API Key、Base URL、Token、温度；连接测试；同步到 LiteLLM；设为某角色默认。
- 数据源配置：新增 / 编辑 / 删除外部数据源（REST API、RSS、NSFC、CNIPA 专利、网页抓取）；指定导入画像类型（技术 / 项目 / 机构 / 人员）；设置定时采集 cron（留空为手动）；按模板填写 JSON 配置；启用 / 停用；点击立即采集。

![图19 系统配置——数据源配置](docs/manual_shots/09b_settings_tab1.png)

- 采集任务：列表每 5 秒自动刷新，展示数据源、画像类型、状态（completed / running / failed / pending）、获取数、导入数、开始时间、耗时；点击"日志"查看任务日志与错误信息。

![图20 系统配置——采集任务](docs/manual_shots/09b_settings_tab2.png)

### 常见的错误

| 现象 | 可能原因 | 处理 |
|---|---|---|
| 服务长期 starting / unhealthy | Elasticsearch 未就绪、migrate 失败、端口占用 | `docker compose logs backend`；等待 ES 60 秒；检查端口 |
| migrate / seed 显示 exited | 属一次性任务，成功后退出 | 非故障，常驻容器 healthy 即可 |
| 前端空白或 502 | nginx 配置或 backend 未 healthy | `docker compose exec frontend nginx -t`；查 `docker compose ps` |
| 搜索无结果 | 未导入数据，ES 无索引 | 先导入画像数据或触发采集 |
| 关联图谱节点不可点击 | 该节点为企业/战略等扩展类型 | 属预期行为，仅四类画像可跳 |
| 跳转后看不到面包屑 | 经分享链接直达或已刷新 | 属预期；仅跳转瞬间携带来源 |
| LLM 抽取/补全无响应 | 未配置模型或 LiteLLM 未就绪 | 系统配置页接入模型并测试连接；查 litellm 日志 |

### 诊断故障处理

```bash
docker compose logs --tail=50 backend
docker compose restart backend
docker compose down -v && docker compose up -d --build
```

第三条会删除全部数据卷、不可恢复，仅作最终手段，执行前务必已备份。

### 信息（接口）

复合后端 Swagger 文档地址：http://localhost:8000/docs 。常用接口示例：

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/v1/profile/tech/search \
  -H "Content-Type: application/json" \
  -d '{"keyword":"量子","page":1,"page_size":10}'
```

### 数据备份与恢复

备份 PostgreSQL：

```bash
docker compose exec postgres pg_dump -U metaprofile metaprofile > backup_$(date +%Y%m%d).sql
```

恢复：

```bash
docker compose exec -T postgres psql -U metaprofile metaprofile < backup_YYYYMMDD.sql
```

Elasticsearch 索引查看与清理：

```bash
curl http://localhost:9200/_cat/indices?v
curl -X DELETE http://localhost:9200/tech_profiles
```

第二条会删除指定索引，执行前确认。

## 附录

### 服务与端口

| 服务 | 端口 | 职责 |
|---|---|---|
| frontend | 80 | React 前端 + nginx 反向代理（按 /api-* 前缀分发） |
| backend | 8000 | 复合后端，聚合画像层 + 分析层 + 配置层全部路由 |
| postgres | 5432 | 主数据库 |
| elasticsearch | 9200 | 全文检索索引 |
| redis | 6379 | 缓存 / 会话 |
| neo4j | 7474 / 7687 | 实体关系图谱 |
| rabbitmq | 5672 / 15672 | 异步任务队列（扫描/采集/选题） |
| litellm | 4000 | 大模型统一代理 |
| migrate | — | 一次性数据库迁移任务 |
| seed | — | 一次性示例数据灌入任务 |

### 目录结构

```
MetaProfile/
├── deploy/                   # 部署配置
│   ├── docker-compose.yml    # 主编排文件
│   ├── .env / .env.example   # 环境变量
│   ├── litellm.yaml          # LLM 代理配置
│   └── pg_init/01_init.sql   # PostgreSQL 初始化
├── frontend/                 # React 前端
│   └── src/{api,pages,components,layouts,utils}
├── metaprofile/              # 后端 Python 包
│   ├── backend/              # 复合后端入口（聚合路由）
│   ├── profile_tech/project/org/person/
│   ├── scan_monitor/
│   ├── new_tech_discovery/
│   └── topic_selection/
├── tests/integration/        # 集成测试
└── docs/                     # 设计文档与手册
```

### 停止与卸载

```bash
cd MetaProfile/deploy
docker compose down        # 停止，保留数据
docker compose down -v     # 停止并删除所有数据卷（不可恢复）
```
