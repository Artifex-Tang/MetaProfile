#!/usr/bin/env bash
# 为已部署的 MetaProfile 栈签发 Let's Encrypt 证书并切到 HTTPS。
#
# 前置(缺一不可):
#   1. 域名已解析 A 记录到本机公网 IP(dig +short 域名 能拿到本机 IP)
#   2. 大陆节点已完成 ICP 备案(否则 80/443 会被运营商拦,challenge 必失败)
#   3. 安全组已放行 80 与 443
#   4. deploy.sh 已跑完,栈在 80 上正常服务
#
# 用法:
#   bash enable_https.sh mp.example.com you@example.com
#   bash enable_https.sh mp.example.com you@example.com --staging   # 先用测试环境试跑,不耗真实配额
set -euo pipefail

DOMAIN="${1:-}"
EMAIL="${2:-}"
STAGING_FLAG=""
[ "${3:-}" = "--staging" ] && STAGING_FLAG="--staging"

if [ -z "$DOMAIN" ] || [ -z "$EMAIL" ]; then
  echo "用法: bash enable_https.sh <域名> <邮箱> [--staging]" >&2
  exit 1
fi

COMPOSE_DIR="${COMPOSE_DIR:-/data/deploy}"
NGINX_DIR="${NGINX_DIR:-/data/nginx}"
CERTS_DIR="${CERTS_DIR:-/data/certs}"
CERTBOT_DIR="${CERTBOT_DIR:-/data/certbot}"
KIT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE="docker compose -f $COMPOSE_DIR/docker-compose.readonly.yml"

echo "=== [1/5] 前置校验 ==="
mkdir -p "$CERTS_DIR" "$CERTBOT_DIR"
resolved="$(getent hosts "$DOMAIN" | awk '{print $1}' | head -1 || true)"
public_ip="$(curl -fsS --max-time 10 https://api.ipify.org || echo '')"
echo "域名解析到: ${resolved:-<解析失败>}"
echo "本机公网 IP: ${public_ip:-<获取失败>}"
if [ -n "$resolved" ] && [ -n "$public_ip" ] && [ "$resolved" != "$public_ip" ]; then
  echo "⚠️  解析地址与本机公网 IP 不一致,HTTP-01 challenge 大概率失败。" >&2
  echo "    确认 A 记录已生效再重试(dig +short $DOMAIN)。" >&2
  read -r -p "仍要继续? [y/N] " ans
  [ "$ans" = "y" ] || exit 1
fi

echo "=== [2/5] 校验 challenge 路径可达 ==="
token="probe-$(date +%s)"
mkdir -p "$CERTBOT_DIR/.well-known/acme-challenge"
echo "$token" > "$CERTBOT_DIR/.well-known/acme-challenge/$token"
if curl -fsS --max-time 10 "http://$DOMAIN/.well-known/acme-challenge/$token" | grep -q "$token"; then
  echo "challenge 路径可达 ✓"
else
  echo "❌ http://$DOMAIN/.well-known/acme-challenge/ 不可达。" >&2
  echo "   查:安全组 80 是否放行 / 备案是否完成 / nginx 是否在跑。" >&2
  exit 1
fi
rm -f "$CERTBOT_DIR/.well-known/acme-challenge/$token"

echo "=== [3/5] certbot 签发证书 ==="
# kit 里带了 certbot 镜像就先离线 load,避免从 docker hub 拉（国内常失败/极慢）。
if ! docker image inspect certbot/certbot >/dev/null 2>&1; then
  if [ -f "$KIT_DIR/certbot-image.tar.gz" ]; then
    echo "  本地 load certbot 镜像…"
    docker load < "$KIT_DIR/certbot-image.tar.gz" | tail -1
  else
    echo "  kit 内无 certbot 镜像，尝试从 docker hub 拉取…"
    docker pull certbot/certbot
  fi
fi
docker run --rm \
  -v "$CERTS_DIR:/etc/letsencrypt" \
  -v "$CERTBOT_DIR:/var/www/certbot" \
  certbot/certbot certonly --webroot -w /var/www/certbot \
  -d "$DOMAIN" --email "$EMAIL" \
  --agree-tos --no-eff-email --non-interactive $STAGING_FLAG

echo "=== [4/5] 切 nginx 到 HTTPS ==="
sed "s/__DOMAIN__/$DOMAIN/g" "$KIT_DIR/nginx/default.https.conf.template" \
  > "$NGINX_DIR/default.conf"
cp "$KIT_DIR/nginx/locations.inc" "$NGINX_DIR/locations.inc"
$COMPOSE exec -T frontend nginx -t
$COMPOSE exec -T frontend nginx -s reload

echo "=== [5/5] 装续期定时任务 ==="
# 证书 90 天有效期,每天两次检查(官方推荐);续期成功才 reload nginx
cat > /etc/cron.d/metaprofile-certbot <<CRON
0 3,15 * * * root docker run --rm -v $CERTS_DIR:/etc/letsencrypt -v $CERTBOT_DIR:/var/www/certbot certbot/certbot renew --webroot -w /var/www/certbot --quiet && $COMPOSE exec -T frontend nginx -s reload
CRON
chmod 0644 /etc/cron.d/metaprofile-certbot

echo
echo "✅ HTTPS 已启用"
echo "   前端     https://$DOMAIN"
echo "   Swagger  https://$DOMAIN/docs"
echo "   MCP      https://$DOMAIN/mcp"
echo
echo "⚠️  MCP 的 Host 白名单:在 $COMPOSE_DIR/.env 里设 MCP_ALLOWED_HOSTS=$DOMAIN"
echo "   然后 $COMPOSE up -d backend 生效(不设=不校验 Host,当前即此状态)。"
