#!/usr/bin/env bash
# MetaProfile 只读云上一键部署脚本(单机 docker)。
# 前置:目标机已装 docker + docker compose,有 /data 数据盘(或改 COMPOSE_DIR)。
# 用法:bash deploy.sh
set -euo pipefail

COMPOSE_DIR="${COMPOSE_DIR:-/data/deploy}"
DIST_DIR="${DIST_DIR:-/data/dist}"
NGINX_DIR="${NGINX_DIR:-/data/nginx}"
CERTS_DIR="${CERTS_DIR:-/data/certs}"
CERTBOT_DIR="${CERTBOT_DIR:-/data/certbot}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-password}"
PG_PASSWORD="${PG_PASSWORD:-metaprofile}"
KIT_DIR="$(cd "$(dirname "$0")" && pwd)"

# ── 前置检查:早失败好过跑到一半炸 ──────────────────────────────
echo "=== [1/9] 前置检查 ==="
fail=0
note() { printf '  %-28s %s\n' "$1" "$2"; }

if command -v docker >/dev/null 2>&1; then
  if docker info >/dev/null 2>&1; then note "docker" "✓ $(docker version --format '{{.Server.Version}}' 2>/dev/null)"
  else note "docker" "✗ 已安装但 daemon 没起(systemctl start docker)"; fail=1; fi
else note "docker" "✗ 未安装"; fail=1; fi

if docker compose version >/dev/null 2>&1; then
  note "docker compose" "✓ $(docker compose version --short 2>/dev/null)"
else note "docker compose" "✗ 缺 compose v2 插件"; fail=1; fi

# 端口占用(80/443 对外;其余绑 127.0.0.1 但仍会占宿主机端口)
if command -v ss >/dev/null 2>&1; then
  busy=""
  for port in 80 443 8000 5432 6379 7474 7687; do
    ss -tln 2>/dev/null | grep -qE "[:.]$port" && busy="$busy $port"
  done
  if [ -n "$busy" ]; then note "端口占用" "✗ 已被占用:$busy"; fail=1
  else note "端口 80/443/…" "✓ 空闲"; fi
else note "端口检查" "- 跳过(无 ss 命令)"; fi

# 磁盘:镜像解开后约需 6G,加数据留 10G
target_fs="$(dirname "$COMPOSE_DIR")"
[ -d "$target_fs" ] || target_fs="/"
avail_g=$(df -BG --output=avail "$target_fs" 2>/dev/null | tail -1 | tr -dc '0-9')
if [ -n "$avail_g" ] && [ "$avail_g" -lt 10 ]; then
  note "磁盘($target_fs)" "✗ 剩余 ${avail_g}G,建议 ≥10G"; fail=1
else note "磁盘($target_fs)" "✓ 剩余 ${avail_g:-?}G"; fi

# kit 完整性
missing=""
for f in mp-all-images.tar.gz dist.tar.gz docker-compose.readonly.yml          mock_data.sql mock_data.cypher nginx/default.conf nginx/locations.inc; do
  [ -f "$KIT_DIR/$f" ] || missing="$missing $f"
done
if [ -n "$missing" ]; then note "kit 完整性" "✗ 缺:$missing"; fail=1
else note "kit 完整性" "✓ 7 项齐全"; fi

if [ "$fail" -ne 0 ]; then
  echo ""
  echo "❌ 前置检查未通过,已中止(没有做任何改动)。修完上面的 ✗ 再重跑。" >&2
  exit 1
fi
echo ""

echo "=== [2/9] docker load images ==="
docker load < "$KIT_DIR/mp-all-images.tar.gz" | tail -5
docker images | grep -E "metaprofile|postgres|neo4j|redis" | head

echo "=== [3/9] 准备目录 + dist ==="
mkdir -p "$DIST_DIR" "$COMPOSE_DIR"
rm -rf "$DIST_DIR"/* 2>/dev/null || true
tar -xzf "$KIT_DIR/dist.tar.gz" -C "$DIST_DIR"
cp "$KIT_DIR/docker-compose.readonly.yml" "$COMPOSE_DIR/"
cp "$KIT_DIR/mock_data.sql" "$KIT_DIR/mock_data.cypher" "$COMPOSE_DIR/"
mkdir -p "$NGINX_DIR" "$CERTS_DIR" "$CERTBOT_DIR"
cp "$KIT_DIR/nginx/default.conf" "$KIT_DIR/nginx/locations.inc" "$NGINX_DIR/"

echo "=== [4/9] compose up(起 5 容器 + migrate)==="
cd "$COMPOSE_DIR"
# MCP Bearer token:首次部署生成一次并落盘,后续重跑复用(否则已发出去的客户端配置会失效)
if [ -f .env ] && grep -q '^MCP_AUTH_TOKEN=..' .env; then
  MCP_AUTH_TOKEN="$(grep '^MCP_AUTH_TOKEN=' .env | head -1 | cut -d= -f2-)"
  echo "  复用已有 MCP token(.env)"
else
  MCP_AUTH_TOKEN="mp_$(od -An -tx1 -N32 /dev/urandom | tr -dc '0-9a-f')"
  touch .env
  sed -i '/^MCP_AUTH_TOKEN=/d' .env
  echo "MCP_AUTH_TOKEN=$MCP_AUTH_TOKEN" >> .env
  echo "  已生成 MCP token 并写入 $COMPOSE_DIR/.env"
fi
export MCP_AUTH_TOKEN
NEO4J_PASSWORD="$NEO4J_PASSWORD" PG_PASSWORD="$PG_PASSWORD" \
  docker compose -f docker-compose.readonly.yml up -d
# 等就绪而不是死等固定秒数:云主机磁盘比开发机慢,60s 可能不够;
# 反过来机器快时也不该白等。最长等 5 分钟,期间每 5s 探一次。
echo "--- 等待各服务就绪(最长 5 分钟)---"
ready=0
for i in $(seq 1 60); do
  if curl -s -o /dev/null --max-time 5 http://localhost:8000/health \
     && curl -s -o /dev/null --max-time 5 http://localhost/; then
    ready=1
    echo "  就绪(用时约 $((i*5))s)"
    break
  fi
  sleep 5
done
if [ "$ready" -ne 1 ]; then
  echo "❌ 等待超时,服务未就绪。查看日志:" >&2
  echo "   cd $COMPOSE_DIR && docker compose -f docker-compose.readonly.yml logs --tail=50" >&2
  docker compose -f docker-compose.readonly.yml ps
  exit 1
fi
docker compose -f docker-compose.readonly.yml ps

echo "=== [5/9] 放宽 NOT NULL(mock 早于 P1/quality 列)==="
docker compose -f docker-compose.readonly.yml exec -T postgres psql -U metaprofile -d metaprofile <<'SQL'
DO $$ DECLARE r record; BEGIN
  FOR r IN SELECT table_name,column_name FROM information_schema.columns
           WHERE table_schema='public' AND is_nullable='NO'
  LOOP
    BEGIN EXECUTE format('ALTER TABLE %I ALTER COLUMN %I DROP NOT NULL', r.table_name, r.column_name);
    EXCEPTION WHEN OTHERS THEN NULL; END;
  END LOOP;
END $$;
SQL

echo "=== [6/9] 灌 mock 数据(pg + neo4j)==="
docker compose -f docker-compose.readonly.yml exec -T postgres psql -U metaprofile -d metaprofile -v ON_ERROR_STOP=1 < mock_data.sql | tail -3
# ⚠️ 必须传 -e JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8:cypher-shell 的 JVM 默认编码非 UTF-8,
# 读 UTF-8 cypher 文件时中文变 '?'(0x3f)存进 neo4j → 关联图谱节点 label 全 ???。
cat mock_data.cypher | docker compose -f docker-compose.readonly.yml exec -T -e JAVA_TOOL_OPTIONS=-Dfile.encoding=UTF-8 neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" --format plain | tail -3

echo "=== [7/9] 补 NULL float(quality 列 mock 不含)==="
docker compose -f docker-compose.readonly.yml exec -T postgres psql -U metaprofile -d metaprofile <<'SQL'
DO $$ DECLARE r record; BEGIN
  FOR r IN SELECT table_name,column_name FROM information_schema.columns
           WHERE table_schema='public' AND data_type='double precision'
  LOOP EXECUTE format('UPDATE %I SET %I=0.5 WHERE %I IS NULL', r.table_name, r.column_name, r.column_name); END LOOP;
END $$;
SQL

echo "=== [8/9] 验证 REST ==="
# 注意:curl -f 撞非 2xx 会 rc=22,配合 set -e 会中断脚本。
# 这里统一去掉 -f 并只取 http_code,让"期望 503"的检查也能正常跑完。
check() {  # check <说明> <url> <期望码>
  # 注意:不能写成 $(curl ... || echo 000)。curl 可能既打印了状态码又非零退出,
  # 两段输出会被拼成 "200000"。必须把失败分支写成赋值,而不是再 echo 一次。
  local code i
  # 重试 5 次:刚起栈时偶发未就绪,一次不中就报 ✗ 会误导人以为部署失败
  for i in 1 2 3 4 5; do
    code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$2") || code=000
    [ -n "$code" ] || code=000
    [ "$code" = "$3" ] && break
    sleep 3
  done
  if [ "$code" = "$3" ]; then echo "  ✓ $1: HTTP $code"; else echo "  ✗ $1: HTTP $code (期望 $3)"; fi
}
check "backend health"  http://localhost:8000/health                      200
check "runtime flags"   http://localhost:8000/api/v1/runtime/flags        200
check "前端首页"        http://localhost/                                  200
check "Swagger(经 80)"  http://localhost/docs                              200
check "LLM 设置熔断"    http://localhost:8000/api/v1/settings/llm          503
check "技术画像统计"    http://localhost/api-tech/api/v1/stats/tech        200

echo "=== [9/9] 验证 MCP(7 个端点)==="
MCP_SLUGS="tech-profile project-profile org-profile person-profile scan-monitor new-tech-discovery topic-selection"
mcp_body='{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"deploy-check","version":"1.0"}}}'
mcp_fail=0
for slug in $MCP_SLUGS; do
  out=$(curl -s --max-time 15 -X POST "http://localhost/mcp/$slug"     -H 'Content-Type: application/json'     -H 'Accept: application/json, text/event-stream'     -H "Authorization: Bearer $MCP_AUTH_TOKEN"     -d "$mcp_body" || echo '')
  if echo "$out" | grep -q '"serverInfo"'; then
    echo "  ✓ /mcp/$slug"
  else
    echo "  ✗ /mcp/$slug  返回: $(echo "$out" | head -c 120)"
    mcp_fail=1
  fi
done
# 无 token 必须被拒,确认鉴权真的生效
naked=$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 -X POST http://localhost/mcp/tech-profile   -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' -d "$mcp_body")
if [ "$naked" = "401" ]; then echo "  ✓ 无 token 访问被拒(401)"; else echo "  ✗ 无 token 访问返回 $naked(期望 401)"; mcp_fail=1; fi

echo ""
echo "✅ 部署完成"
echo "   前端     http://<本机公网IP>        (注意 http:// 前缀,Chrome 别自动跳 HTTPS)"
echo "   7 工具   http://<IP>/tech?embed=1   (另 /project /org /person /scan /discovery /topics)"
echo "   Swagger  http://<IP>/docs"
echo ""
echo "   MCP 端点(7 个,共 37 个只读工具):"
for slug in $MCP_SLUGS; do echo "     http://<IP>/mcp/$slug"; done
echo "   MCP token: $MCP_AUTH_TOKEN"
echo "   生成客户端配置:"
echo "     docker compose -f docker-compose.readonly.yml exec -T backend \\"
echo "       python scripts/gen_mcp_config.py --base-url http://<IP> --token \$MCP_AUTH_TOKEN"
echo ""
echo "启用 HTTPS(需域名 + 已备案 + 80/443 放行):"
echo "   bash $KIT_DIR/enable_https.sh <域名> <邮箱>"
