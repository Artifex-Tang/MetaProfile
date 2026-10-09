# MetaProfile 只读云上部署手册

单机 Docker 一键部署(去 Doris 的轻量只读版)。

## 系统要求

- Linux 主机(Ubuntu 22.04+/CentOS 等),**8C 16G+**(neo4j 吃内存,推荐 32G)
- 已装 **docker + docker compose**(compose v2)
- 数据盘挂 `/data`(可选,无则用系统盘)
- 公网放行 **80 + 443**(浏览器访问 / certbot 签发)+ 22(SSH)
- 其余端口(8000/5432/6379/7474/7687)已改为只绑 `127.0.0.1`,**不需要也不应该对外放行**

## 包内容

| 文件 | 说明 |
|------|------|
| `mp-all-images.tar.gz` | 5 镜像(backend/frontend/postgres/neo4j/redis) |
| `dist.tar.gz` | 前端静态 dist(bind mount,免 rebuild) |
| `docker-compose.readonly.yml` | 只读栈编排(5 容器,MODE=readonly) |
| `mock_data.sql` / `mock_data.cypher` | 演示数据(37×4 实体 + 652 关系) |
| `nginx/` | nginx 配置(`default.conf` HTTP 版 + `locations.inc` 共享路由 + HTTPS 模板) |
| `.env.example` | 凭据模板(PG/NEO4J 密码、MCP Host 白名单) |
| `deploy.sh` | 一键部署脚本 |
| `enable_https.sh` | 签发 Let's Encrypt 证书并切到 HTTPS |

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

## MCP 服务（7 个独立端点）

一个工具一个 MCP 端点，路径 `/mcp/<slug>`，经 nginx 走 80/443，不需要单独开端口。

| 端点 | 客户端配置键 | 工具数 | 工具 |
|---|---|---|---|
| `/mcp/tech-profile` | `techProfile` | 8 | search_profiles / get_profile / batch_get_profiles / get_profile_stats / list_profile_changes / get_relations / find_relation_path / **get_tech_relation** |
| `/mcp/project-profile` | `projectProfile` | 7 | 同上（无 get_tech_relation） |
| `/mcp/org-profile` | `orgProfile` | 7 | 同上 |
| `/mcp/person-profile` | `personProfile` | 7 | 同上 |
| `/mcp/scan-monitor` | `scanMonitor` | 3 | list_frontier_tech / list_frontier_alerts / get_frontier_tech |
| `/mcp/new-tech-discovery` | `newTechDiscovery` | 3 | list_new_tech / list_tech_signals / get_signal_network |
| `/mcp/topic-selection` | `topicSelection` | 2 | list_topics / get_topic |

合计 **37 个工具，全部只读**。画像类型绑定在端点上，工具参数里不再有 `profile_type`。

写入 / 导入 / LLM 补全 / 触发扫描的接口一个都没暴露——只读栈里它们本就 503 或缺依赖。
semantic-search 依赖 Elasticsearch，只读栈已裁掉，同样未暴露。

### 鉴权

`MCP_AUTH_TOKEN`（compose 环境变量，`deploy.sh` 首次部署自动生成写进 `/data/deploy/.env`）。
带 `Authorization: Bearer <token>` 才放行，否则 401。留空则不校验。

`MCP_ALLOWED_HOSTS` 控制 DNS rebinding 防护：留空不校验 Host；填域名则只放行该 Host。

### 生成客户端配置

```bash
cd /data/deploy && C="docker compose -f docker-compose.readonly.yml"
TOKEN=$(grep '^MCP_AUTH_TOKEN=' .env | cut -d= -f2-)
$C exec -T backend python scripts/gen_mcp_config.py --base-url https://<域名> --token "$TOKEN"
$C exec -T backend python scripts/gen_mcp_config.py --base-url https://<域名> --token "$TOKEN" --combined
```

### 实现要点

- 全部端点挂在 backend 同一进程，工具经**回环 HTTP** 调本应用的 `/api/v1`
  （复用 readonly_guard 熔断与 pydantic 校验，不重复一套逻辑）
- 挂载点是 `/`（兜底），每个端点用自己的绝对路径 `/mcp/<slug>` 注册；
  挂到 `/mcp` 会让裸路径被 Starlette 的 redirect_slashes 307 走，而 MCP 客户端普遍不跟随重定向
- nginx 的 `location /mcp` 关了 `proxy_buffering`，SSE 长连接才不会被缓冲住

## 启用 HTTPS

**前置(缺一不可)**:

1. 域名已注册,A 记录解析到本机公网 IP(`dig +short <域名>` 能拿到)
2. **大陆节点需完成 ICP 备案**(7~20 工作日),否则 80/443 被运营商拦,签发必失败
3. 安全组放行 80 与 443
4. `deploy.sh` 已跑完,栈在 80 上正常服务

```bash
# 先用 staging 试跑(不消耗 Let's Encrypt 真实配额,每域名每周 5 次限制)
bash enable_https.sh mp.example.com you@example.com --staging
# 通了再签正式证书
bash enable_https.sh mp.example.com you@example.com
```

脚本做的事:校验解析与 challenge 路径可达 → certbot webroot 签发 → 渲染 HTTPS nginx 配置(80 跳 443)→ `nginx -t` 校验后 reload → 装 `/etc/cron.d/metaprofile-certbot` 自动续期(每天 3 点/15 点检查)。

证书落在 `/data/certs`,challenge 走 `/data/certbot`,两者都是 bind mount,重建容器不丢。

启用后记得把 `MCP_ALLOWED_HOSTS=<域名>` 写进 `/data/deploy/.env` 并 `docker compose ... up -d backend`。

**无域名的退路**:自签证书浏览器会红警告,给第三方测试不合适;或换香港/新加坡节点免备案。

## 模拟数据

kit 里的 `mock_data.sql`(PostgreSQL)与 `mock_data.cypher`(Neo4j)是**已生成好的**演示数据,
`deploy.sh` 会自动灌,不需要额外操作。默认 37×4 实体 + 652 关系。

### 重新生成(换数量 / 换种子)

生成器 `scripts/gen_mock_data.py` 已经打进 backend 镜像,可以直接在云上重生成:

```bash
cd /data/deploy
COMPOSE="docker compose -f docker-compose.readonly.yml"

# 在容器里生成(--sql-only 不连库,只吐文件),每类 60 个实体
$COMPOSE exec -T backend python scripts/gen_mock_data.py --sql-only --count 60

# 取出生成的文件
docker cp $($COMPOSE ps -q backend):/app/deploy/mock_data.sql   ./mock_data.sql
docker cp $($COMPOSE ps -q backend):/app/deploy/mock_data.cypher ./mock_data.cypher

# 清库重灌(down -v 会删卷,数据全没,确认后再执行)
$COMPOSE down -v && $COMPOSE up -d && sleep 60
bash deploy.sh      # 重跑会重新放宽 NOT NULL + 灌新数据
```

也可以在开发机上生成后重打 kit:`python scripts/build_kit.py --regen-mock 60`。

### 两个必须知道的点

1. **灌 Neo4j 必须带 `JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8`**。cypher-shell 的 JVM 默认
   编码不是 UTF-8,读 UTF-8 的 cypher 文件会把中文解成 `?`(0x3f)存进去,表现为关联图谱
   节点标签全是 `???`。`deploy.sh` 已经带了,手动灌的时候别漏。
2. **灌之前必须先放宽 NOT NULL**。生成器目前不输出 P1 新增的列(`tech_layer` 等),
   而 schema 里它们是 NOT NULL,直接灌会违反约束导致整个事务 ROLLBACK。
   `deploy.sh` 第 4 步的 DO block 干的就是这件事。

> 生成器对集合字段的迭代序没有锁死,同参数重跑会得到内容等价但行序不同的文件。
> 不影响功能,但会让 git diff 很吵,所以 `build_kit.py` 默认不重新生成。

## 验证清单

- `http://<IP>/` → 前端首页
- 4 画像(技术/项目/机构/人员)详情页可打开,关系图谱显示
- 新技术发现页:关联列(技术/机构/人员 N)可点开网络图
- 熔断端点返 503:`curl http://<IP>/api-settings/api/v1/settings/llm`(只读模式)
- Swagger 可打开:`http://<IP>/docs`
- MCP 握手成功:
  ```bash
  curl -s -X POST http://<IP>/mcp     -H 'Content-Type: application/json'     -H 'Accept: application/json, text/event-stream'     -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"probe","version":"1.0"}}}'
  # 返回里应含 "serverInfo":{"name":"metaprofile"...}
  ```

## 架构

```
单机 Docker
├── frontend (nginx:80/443, mount dist + nginx conf.d + certs)  ← 对外 80/443
├── backend  (uvicorn:8000 仅绑 127.0.0.1, MODE=readonly 熔断 ODS/LLM/画像写)
│              └── /mcp  MCP 服务(15 个只读工具,回环调自己的 /api/v1)
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
# 注:nginx 配置现在挂的是整个目录 /data/nginx → /etc/nginx/conf.d
```

## 改后端

后端源码在镜像内。改码需 rebuild 镜像:
```bash
docker build -t metaprofile-backend:latest .
docker compose -f docker-compose.readonly.yml up -d --force-recreate backend
```
或改 compose backend 加 `volumes: [./metaprofile:/app/metaprofile:ro]` bind mount 源码(镜像只 deps),改码 scp + restart。
