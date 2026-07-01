# MetaProfile 只读云上部署手册

单机 Docker 一键部署(去 Doris 的轻量只读版)。

## 系统要求

- Linux 主机(Ubuntu 22.04+/CentOS 等),**8C 16G+**(neo4j 吃内存,推荐 32G)
- 已装 **docker + docker compose**(compose v2)
- 数据盘挂 `/data`(可选,无则用系统盘)
- 公网放行 **80**(浏览器访问)+ 22(SSH)

## 包内容

| 文件 | 说明 |
|------|------|
| `mp-all-images.tar.gz` | 5 镜像(backend/frontend/postgres/neo4j/redis) |
| `dist.tar.gz` | 前端静态 dist(bind mount,免 rebuild) |
| `docker-compose.readonly.yml` | 只读栈编排(5 容器,MODE=readonly) |
| `mock_data.sql` / `mock_data.cypher` | 演示数据(37×4 实体 + 652 关系) |
| `.env.example` | 凭据模板(PG/NEO4J 密码) |
| `deploy.sh` | 一键部署脚本 |

## 部署步骤

### 1. 解包
```bash
tar -xzf metaprofile-deploy-kit.tar.gz
cd metaprofile-deploy-kit
```

### 2.(可选)挂数据盘到 /data
若主机有独立数据盘(避免占系统盘):
```bash
mkfs.ext4 -F /dev/vdb
mkdir -p /data && mount /dev/vdb /data
# docker data-root 迁 /data/docker(可选,一劳永逸)
echo '{"data-root":"/data/docker"}' | sudo tee /etc/docker/daemon.json
# 注意:若 daemon.json 已有 registry-mirrors,合并 data-root 字段
systemctl restart docker
```

### 3. 一键部署
```bash
bash deploy.sh
```
脚本自动:load 镜像 → 解 dist → compose up → migrate 建表 → 放宽 NOT NULL(mock 早于 P1/quality 列)→ 灌 mock 数据 → 补 NULL float → 验证。

约 3-5 分钟(灌数据 + 起栈)。

### 4. 访问
浏览器开 `http://<主机公网IP>`(**注意 http:// 前缀**,Chrome 默认 HTTPS 会失败)。

左侧导航:总览 / 技术画像 / 项目画像 / 机构画像 / 人员画像 / 扫描监测 / 新技术发现 / 选题服务 / 系统配置。

> "关系探索"已隐藏;画像详情页"LLM 补全"按钮已隐藏(只读模式)。

## 验证清单

- `http://<IP>/` → 前端首页
- 4 画像(技术/项目/机构/人员)详情页可打开,关系图谱显示
- 新技术发现页:关联列(技术/机构/人员 N)可点开网络图
- 熔断端点返 503:`curl http://<IP>:8000/api/v1/settings/llm`(只读模式)

## 架构

```
单机 Docker
├── frontend (nginx:80, mount dist)  ← 对外 80
├── backend  (uvicorn:8000, MODE=readonly 熔断 ODS/LLM/画像写)
├── postgres:15   (profile + 配置,mock 37×4)
├── neo4j:5.16    (148 节点 + 652 关系)
└── redis:7       (stats cache)
```
- 去:Doris / ES / rabbitmq / litellm / worker(只读不跑 LLM/采集)
- `MODE=readonly` → backend 中间件 `readonly_guard` 拦 ODS/采集/LLM/画像写(PUT/import/enrich)→ 503;GET/search/分析层全通

## 常见坑

1. **Chrome HTTPS-first**:输纯 IP 默认试 HTTPS → 显式输 `http://<IP>`。
2. **代理(clash/v2ray)**:浏览器走代理可能 502 → 代理 bypass 加主机 IP,或关代理。
3. **backend recreate 后 frontend 502**:nginx.conf 已用 `resolver 127.0.0.11 valid=10s` 运行时解析 backend,10s 内自动重解析。若仍 502,`docker compose restart frontend`。
4. **mock_data schema 漂移**:P1 给 tech_profile 加 NOT NULL 列(tech_layer 等),mock 老不含 → `deploy.sh` 已 DROP NOT NULL 放宽。重灌数据须先 DROP NOT NULL。
5. **重置数据**:`docker compose down -v` 清卷后重跑 `deploy.sh`(从头灌)。

## 改前端(免 rebuild 镜像)

dist 是 bind mount,改前端只需:
```bash
# 本地
cd frontend && npm run build
tar -C frontend/dist -czf dist.tar.gz .
scp dist.tar.gz <host>:/data/
# 主机
rm -rf /data/dist/* && tar -xzf /data/dist.tar.gz -C /data/dist
# nginx 自动 serve 新 dist(无需 restart)
```

## 改后端

后端源码在镜像内。改码需 rebuild 镜像:
```bash
docker build -t metaprofile-backend:latest .
docker compose -f docker-compose.readonly.yml up -d --force-recreate backend
```
或改 compose backend 加 `volumes: [./metaprofile:/app/metaprofile:ro]` bind mount 源码(镜像只 deps),改码 scp + restart。
