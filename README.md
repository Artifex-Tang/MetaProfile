# MetaProfile — 重点目标对象跟踪系统

MetaProfile 是产业技术情报分析的重点目标对象跟踪系统，对应课题任务书指标 4.2 中的 **7 个工具**：

- 4 个画像工具：产业前沿科技技术画像、产业重大科技项目画像、产业前沿科技机构画像、产业重点人物画像
- 3 个分析工具：产业前沿技术扫描监测、产业新技术发现、产业科技动态选题

## 系统架构（三层）

```
┌────────────────────────────────────────────────────────┐
│ 分析层  scan_monitor / new_tech_discovery / topic_selection │
└────────────────────────────────────────────────────────┘
                       ▲ REST
┌────────────────────────────────────────────────────────┐
│ 画像层  profile_tech / profile_project / profile_org / profile_person │
└────────────────────────────────────────────────────────┘
                       ▲ 内部调用
┌────────────────────────────────────────────────────────┐
│ 底座层  foundation                                      │
│ collectors → cleaners → ner → extractors → relation →   │
│ disambiguation → storage → enrichment → stats           │
└────────────────────────────────────────────────────────┘
                       ▲
┌────────────────────────────────────────────────────────┐
│ 共享层  shared (config / db / llm / nlp / schemas / utils) │
└────────────────────────────────────────────────────────┘
```

## 技术栈

Python 3.11+, FastAPI 0.110+, SQLAlchemy 2.0 (async), Pydantic v2, PostgreSQL 15, Elasticsearch 8.x, Neo4j 5, Redis 7, RabbitMQ, Celery 5, LiteLLM Proxy（Qwen2.5-72B / DeepSeek）, BGE-large-zh-v1.5

## 实现指引

详见 [`CLAUDE_CODE_PLAN.md`](./CLAUDE_CODE_PLAN.md)。

## 启动方式

```bash
# 依赖安装
pip install -e .

# 启动 4 个画像服务
uvicorn metaprofile.profile_tech.main:app    --port 8001
uvicorn metaprofile.profile_project.main:app --port 8002
uvicorn metaprofile.profile_org.main:app     --port 8003
uvicorn metaprofile.profile_person.main:app  --port 8004

# 启动 3 个分析服务
uvicorn metaprofile.scan_monitor.main:app        --port 8101
uvicorn metaprofile.new_tech_discovery.main:app  --port 8102
uvicorn metaprofile.topic_selection.main:app     --port 8103

# 启动 Celery worker
celery -A metaprofile.profile_tech.workers.celery_app worker -l info
celery -A metaprofile.profile_tech.workers.celery_app beat   -l info
```

或使用 docker-compose：

```bash
cd deploy && docker-compose up -d
```

## 目录结构

```
code/
├── CLAUDE_CODE_PLAN.md          ← 实现指引（必读）
├── README.md
├── pyproject.toml
├── deploy/
│   ├── docker-compose.yml
│   └── migrations/              ← Alembic 迁移
├── docs/
├── scripts/                     ← 运维脚本
├── tests/
└── metaprofile/
    ├── shared/                  ← 共享层
    ├── foundation/              ← 底座层
    ├── profile_tech/            ← 技术画像
    ├── profile_project/         ← 项目画像
    ├── profile_org/             ← 机构画像
    ├── profile_person/          ← 人员画像
    ├── scan_monitor/            ← 扫描监测
    ├── new_tech_discovery/      ← 新技术发现
    ├── topic_selection/         ← 动态选题
    └── api_gateway/             ← 统一网关
```
