#!/usr/bin/env bash
# MetaProfile 只读云上一键部署脚本(单机 docker)。
# 前置:目标机已装 docker + docker compose,有 /data 数据盘(或改 COMPOSE_DIR)。
# 用法:bash deploy.sh
set -euo pipefail

COMPOSE_DIR="${COMPOSE_DIR:-/data/deploy}"
DIST_DIR="${DIST_DIR:-/data/dist}"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-password}"
PG_PASSWORD="${PG_PASSWORD:-metaprofile}"
KIT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== [1/7] docker load images ==="
docker load < "$KIT_DIR/mp-all-images.tar.gz" | tail -5
docker images | grep -E "metaprofile|postgres|neo4j|redis" | head

echo "=== [2/7] 准备目录 + dist ==="
mkdir -p "$DIST_DIR" "$COMPOSE_DIR"
rm -rf "$DIST_DIR"/* 2>/dev/null || true
tar -xzf "$KIT_DIR/dist.tar.gz" -C "$DIST_DIR"
cp "$KIT_DIR/docker-compose.readonly.yml" "$COMPOSE_DIR/"
cp "$KIT_DIR/mock_data.sql" "$KIT_DIR/mock_data.cypher" "$COMPOSE_DIR/"
cp "$KIT_DIR/nginx.conf" /data/nginx.conf   # frontend bind mount

echo "=== [3/7] compose up(起 5 容器 + migrate)==="
cd "$COMPOSE_DIR"
NEO4J_PASSWORD="$NEO4J_PASSWORD" PG_PASSWORD="$PG_PASSWORD" \
  docker compose -f docker-compose.readonly.yml up -d
echo "--- 等 60s 栈起来 ---"
sleep 60
docker compose -f docker-compose.readonly.yml ps

echo "=== [4/7] 放宽 NOT NULL(mock 早于 P1/quality 列)==="
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

echo "=== [5/7] 灌 mock 数据(pg + neo4j)==="
docker compose -f docker-compose.readonly.yml exec -T postgres psql -U metaprofile -d metaprofile -v ON_ERROR_STOP=1 < mock_data.sql | tail -3
cat mock_data.cypher | docker compose -f docker-compose.readonly.yml exec -T neo4j cypher-shell -u neo4j -p "$NEO4J_PASSWORD" --format plain | tail -3

echo "=== [6/7] 补 NULL float(quality 列 mock 不含)==="
docker compose -f docker-compose.readonly.yml exec -T postgres psql -U metaprofile -d metaprofile <<'SQL'
DO $$ DECLARE r record; BEGIN
  FOR r IN SELECT table_name,column_name FROM information_schema.columns
           WHERE table_schema='public' AND data_type='double precision'
  LOOP EXECUTE format('UPDATE %I SET %I=0.5 WHERE %I IS NULL', r.table_name, r.column_name, r.column_name); END LOOP;
END $$;
SQL

echo "=== [7/7] 验证 ==="
echo -n "health:  "; curl -sf http://localhost:8000/health; echo
echo -n "flags:   "; curl -sf http://localhost:8000/api/v1/runtime/flags; echo
echo -n "frontend:"; curl -sf -o /dev/null -w " HTTP %{http_code}\n" http://localhost/
echo -n "llm 熔断:"; curl -sf -o /dev/null -w " HTTP %{http_code} (期望 503)\n" http://localhost:8000/api/v1/settings/llm

echo ""
echo "✅ 部署完成。浏览器开 http://<本机公网IP> (注意 http:// 前缀,Chrome 别走 HTTPS)"
