# MCP 客户端配置（模板）

这两个文件是 7 个 MCP 工具的客户端配置**模板**，分发给使用方前要把占位符替换成真实值。

| 文件 | 用途 |
|------|------|
| `mcp_clients_combined.json` | **合并版**，一份配置挂全部 7 个端点。适合自己用 / 一次挂齐 |
| `mcp_clients.md` | **分段版**，7 段独立配置，每段一个工具。适合分发给不同的人，各取所需 |

## 两个占位符

```
YOUR_HOST        → 部署机地址（http://47.120.41.179 或 https://你的域名）
YOUR_MCP_TOKEN   → MCP_AUTH_TOKEN（部署时自动生成，见下）
```

## 拿真实 token

`deploy.sh` 首次部署时生成，写在部署机的 `/data/deploy/.env`：

```bash
grep MCP_AUTH_TOKEN /data/deploy/.env
# MCP_AUTH_TOKEN=mp_03781446ba8676975aadfcc6e70977f66ee44599a683e66c392e066f9fb0572b
```

`Bearer ` 后面那一长串就是 `YOUR_MCP_TOKEN`。

## 重新生成（填好真实值）

部署机上跑（已经填好 host 和 token，不用手改）：

```bash
cd /data/deploy
C="docker compose -f docker-compose.readonly.yml"
TOKEN=$(grep '^MCP_AUTH_TOKEN=' .env | cut -d= -f2-)

# 合并版
$C exec -T backend python scripts/gen_mcp_config.py \
  --base-url http://47.120.41.179 --token "$TOKEN" --combined \
  --output mcp_clients_combined.json

# 分段版
$C exec -T backend python scripts/gen_mcp_config.py \
  --base-url http://47.120.41.179 --token "$TOKEN" \
  --output mcp_clients.md
```

上了 HTTPS 把 `--base-url` 换成 `https://你的域名`。

## 7 个端点速查

| # | 工具 | 配置键 | 端点 | 工具数 |
|---|------|--------|------|--------|
| 1 | 技术画像工具 | `techProfile` | `/mcp/tech-profile` | 8 |
| 2 | 项目画像工具 | `projectProfile` | `/mcp/project-profile` | 7 |
| 3 | 机构画像工具 | `orgProfile` | `/mcp/org-profile` | 7 |
| 4 | 人员画像工具 | `personProfile` | `/mcp/person-profile` | 7 |
| 5 | 扫描监测工具 | `scanMonitor` | `/mcp/scan-monitor` | 3 |
| 6 | 新技术发现工具 | `newTechDiscovery` | `/mcp/new-tech-discovery` | 3 |
| 7 | 选题服务工具 | `topicSelection` | `/mcp/topic-selection` | 2 |

合计 **37 个工具，全部只读**。无 token 访问返 401。
