# 本地 Doris 基础设施搭建 · 详细操作手册

- 日期：2026-06-17
- 目的：本地起一个与云端**同方言**的 Apache Doris（2.1.11），镜像 `ods_zbzx`，供画像抽取管线**快速本地读**；云端兜底/取最新。
- 平台：Windows 11 + Docker Desktop + git-bash。
- 配套脚本：`_doris_ddl_sync.py`（DDL 同步）、`_load_chunked*.py`（数据同步，改目标）。
- 上游设计：`docs/superpowers/specs/2026-06-17-ods-profile-extraction-design.md`。

> 说明：本手册把"搭建 + 同步 + 运维 + 排错"全写出来，目标是**你能照着手动跑完**。每步都有可复制的命令 + 预期结果 + 出错怎么办。

---

## 0. 前置条件（先逐项确认）

| 项 | 要求 | 检查命令（git-bash） |
|---|---|---|
| Docker Desktop | 已装、正在运行、Linux 容器模式 | `docker version` 两个 client/server 都有 |
| 磁盘 | **H 盘可用 ≥ 200GB**（结构化主表阶段；全量附件需 1TB+） | `df -h /h` |
| 内存 | ≥ 8GB 空闲给 BE（主机 31GB 够） | 任务管理器看 |
| 端口 | **9030 / 8030 / 8040 / 9050** 空闲（9030 若被占见 §9） | `netstat -ano \| findstr 9030` |
| 网络 | **Clash TUN 关**（开着→云同步 0.04MB/s；关了→企业 VPN ~2.4MB/s）。System Proxy 保留。 | Clash 界面看 TUN 开关实物 |
| Python | 3.12 + pymysql（已装且已 patch） | `python -c "import pymysql"` |
| 云端可达 | 小查询秒回 | `python _explore_doris.py` 跑通 |

**⚠️ TUN 必须关。** 这是 memory `ods-mirror-mysql` 多次踩过的坑：TUN 开 = 10.242.0.1 被套代理中转 = 40KB/s；TUN 关 = 宿主走企业 VPN 直连 = 2.4MB/s。Claude Code 走 HTTP_PROXY=127.0.0.1:7890 不受 TUN 关影响。

---

## 1. 部署规划

- Doris 版本：**2.1.11**（与云端 `doris-2.1.11-rc01` 对齐，避免方言差异）。
- 镜像：`apache/doris:doris-2.1.11-fe`、`apache/doris:doris-2.1.11-be`。
- 形态：**1 FE + 1 BE**（本地开发，单副本）。
- 网络：自建 docker bridge `dorisnet`，固定 IP（FE=172.28.80.10，BE=172.28.80.20），靠 `priority_networks` 锁定通告地址。
- 端口映射（宿主→容器）：
  - `127.0.0.1:9030 → fe:9030`（MySQL 协议，**提取器/客户端连这个**）
  - `127.0.0.1:8030 → fe:8030`（FE Web UI）
  - `127.0.0.1:8040 → be:8040`（BE Web UI）
- 数据卷：**H 盘**（`H:/docker/doris/{fe,be}/...`），与现有 mp-mysql 同策略（C 盘只剩 29G）。

---

## 2. 写配置文件

在仓库根 `E:\ccode\MetaProfile` 下建 `docker/doris/` 目录，放 4 个文件。

### 2.1 `docker/doris/docker-compose.yml`

```yaml
version: "3"
services:
  doris-fe:
    image: apache/doris:doris-2.1.11-fe
    container_name: mp-doris-fe
    hostname: fe
    environment:
      FE_SERVERS: "fe1:172.28.80.10:9010:9020:9030"
      FE_ID: "1"
      PRIORITY_NETWORKS: "172.28.80.0/24"
    ports:
      - "127.0.0.1:8030:8030"
      - "127.0.0.1:9030:9030"
    volumes:
      - H:/docker/doris/fe/doris-meta:/opt/apache-doris/fe/doris-meta
      - H:/docker/doris/fe/log:/opt/apache-doris/fe/log
      - ./fe.conf:/opt/apache-doris/fe/conf/fe.conf
    networks:
      dorisnet:
        ipv4_address: 172.28.80.10
    restart: unless-stopped

  doris-be:
    image: apache/doris:doris-2.1.11-be
    container_name: mp-doris-be
    hostname: be
    environment:
      PRIORITY_NETWORKS: "172.28.80.0/24"
      BE_ADDR: "172.28.80.20:9050"
    volumes:
      - H:/docker/doris/be/storage:/opt/apache-doris/be/storage
      - H:/docker/doris/be/log:/opt/apache-doris/be/log
      - ./be.conf:/opt/apache-doris/be/conf/be.conf
    ports:
      - "127.0.0.1:8040:8040"
    depends_on: [doris-fe]
    networks:
      dorisnet:
        ipv4_address: 172.28.80.20
    restart: unless-stopped

networks:
  dorisnet:
    driver: bridge
    ipam:
      config:
        - subnet: 172.28.80.0/24
```

> H 盘路径需先建好目录（见 §3 步骤1）。Windows 下 `H:/docker/...` 在 compose 里用正斜杠。

### 2.2 `docker/doris/fe.conf`（关键覆盖项）

```ini
# 网络：锁定 docker 子网，避免通告成容器内不可达地址
priority_networks = 172.28.80.0/24

# 端口（与镜像默认一致，显式写更稳）
edit_log_port = 9010
query_port = 9030
http_port = 8030
rpc_port = 9020

# 内存（本地单节点，保守）
JAVA_OPTS="-Xmx2048m -XX:+UseG1GC"
```

### 2.3 `docker/doris/be.conf`（关键覆盖项）

```ini
priority_networks = 172.28.80.0/24

be_port = 9050
webserver_port = 8040
heartbeats_service_port = 9050
brpc_port = 8060

# 内存上限（按主机空闲调，8GB 够结构化阶段）
mem_limit = 8g

# 存储
storage_root_path = /opt/apache-doris/be/storage
```

> `heartbeats_service_port` 与 `be_port` 在 2.1 默认都是 9050（heartbeat 复用 be_port），保持默认即可，不要乱改。

---

## 3. 启动集群（逐步）

**步骤 1 — 建目录（H 盘卷）：**
```bash
mkdir -p /h/docker/doris/fe/doris-meta /h/docker/doris/fe/log \
         /h/docker/doris/be/storage /h/docker/doris/be/log
```

**步骤 2 — 拉镜像 + 起服务：**
```bash
cd /e/ccode/MetaProfile/docker/doris
docker compose pull        # 拉两个镜像（各 ~2GB，首次慢）
docker compose up -d
docker compose ps          # 期望 mp-doris-fe / mp-doris-be 都 Up
```

**步骤 3 — 等 FE 就绪（约 20-40s）：**
```bash
docker logs -f mp-doris-fe
# 看到 "thrift server started" / "QE service start" 即 OK，Ctrl+C 退出日志
```

**步骤 4 — 加 BE 到 FE（关键，只做一次）：**
```bash
docker exec -it mp-doris-fe mysql -h 127.0.0.1 -P 9030 -u root
# 进 mysql 后：
ALTER SYSTEM ADD BACKEND "172.28.80.20:9050";
SHOW BACKENDS\G
# 期望看到一行 172.28.80.20，Alive=true，HeartbeatPort=9050
exit;
```
> 若报 "backend already exists" → 已加过，忽略。
> 若 `SHOW BACKENDS` 里 Alive=false：BE 没起来或 priority_networks 没生效，见 §9。

**步骤 5 — 建库 + 设 root 密码（可选）：**
```bash
docker exec -it mp-doris-fe mysql -h 127.0.0.1 -P 9030 -u root -e \
  "CREATE DATABASE IF NOT EXISTS ods_zbzx;"
# 设密码（建议，与系统注册一致）：本地开发可留空，密码留空时 _doris_ddl_sync.py LOCAL.password="" 即可
# docker exec -it mp-doris-fe mysql ... -e "SET PASSWORD FOR 'root' = PASSWORD('mp_local_2026');"
```

**步骤 6 — 验证连通（宿主）：**
```bash
python -c "import pymysql; c=pymysql.connect(host='127.0.0.1',port=9030,user='root',database='ods_zbzx'); print('LOCAL DORIS OK', c.get_server_info())"
```
期望：`LOCAL DORIS OK 5.7.99`（Doris MySQL 协议伪装成 5.7）。

---

## 4. 同步表结构（DDL，零转换）

云端是 Doris，本地也是 Doris → DDL 直接搬，只把**副本数 3→1**（单 BE）。

**生成 + 应用：**
```bash
cd /e/ccode/MetaProfile
python _doris_ddl_sync.py          # 只生成 _doris_local_schema.sql（先看一眼）
python _doris_ddl_sync.py --apply  # 生成 + 应用到本地
```

预期输出：`云端表数: 39` → `已写 _doris_local_schema.sql（39 表）` → 本地应用 39 张 `CREATE TABLE`。

**验证：**
```bash
docker exec -it mp-doris-fe mysql -h 127.0.0.1 -P 9030 -u root ods_zbzx -e "SHOW TABLES" | wc -l
# 期望 40（39 表 + 1 表头）
```

> 脚本逻辑：`SHOW CREATE TABLE` 全表 → 正则改 `replication_allocation` 3→1 → `DROP TABLE IF EXISTS` + 建表，幂等可重跑。
> 若某表建失败（如带 PARTITION/资源组属性），脚本会 `SKIP: <err>` 打印，逐个手动处理（通常改副本数即可）。

---

## 5. 同步数据（云 → 本地）

### 5.1 策略（分阶段，控体积 + WAN 瓶颈）

| 阶段 | 表 | 云端量 | 目的 |
|---|---|---|---|
| P1 结构化主表（先） | science/patent/policy/industry/market/news/financial/talent/key_events | ~126GB | 画像抽取主燃料 |
| P2 company_basic_info | company_basic_info 429M | ~304GB | Org 全量（最大） |
| P3 附件（按需） | *_attachment 的 clean_content | ~1.1TB | 内容挖掘（设计里 `content_mine_filter` 控制，可后补） |

### 5.2 改 loader 目标到本地 Doris

现有 `_load_chunked.py` / `_load_chunked_big.py` 当前写 mp-mysql(3307)。改成本地 Doris：

**编辑 `_load_chunked.py` 顶部目标连接**（把 MySQL DSN 换成本地 Doris）：
```python
# 原（MySQL 镜像）：
# DEST = dict(host="127.0.0.1", port=3307, user="root", password="mp_dev_2026", database="ods_zbzx", ...)
# 改（本地 Doris）：
DEST = dict(host="127.0.0.1", port=9030, user="root", password="", database="ods_zbzx",
            charset="utf8mb4")
```

**注意 Doris 与 MySQL 的差异（loader 要点）：**
1. **去重**：Doris 无 `INSERT IGNORE`。用 Doris Unique Key 模型表自然去重，或 loader 先 `DELETE FROM t WHERE id BETWEEN ...` 再插。最简：表建成 Unique Key(id) ——但云端是 DUPLICATE KEY。**推荐**：loader 用"先 DELETE 窗口再 INSERT"做续传（替代 INSERT IGNORE）。
2. **流式插入**：pymysql 逐行 INSERT 对 Doris 较慢（Doris 偏批）。**优化**：用 **Stream Load**（HTTP `PUT /api/{db}/{table}/_stream_load`，CSV/JSON），单次几万行。loader 可加 stream-load 分支。WAN 是主瓶颈，先 pymysql 跑通再优化。
3. **大表分窗**：复用 `_load_chunked_big.py` 的 COUNT 二分 id 窗（绕云端 BE OOM），这点不变（瓶颈在云端读，与目标引擎无关）。
4. **字符集**：Doris 默认 `utf8mb4`，pymysql 已 patch 脏字节处理，沿用。

**P1 启动（小表先，验证链路）：**
```bash
# powershell Start-Process 脱离（git-bash nohup& 会杀子，memory 教训）
powershell Start-Process python -ArgumentList '-u','E:/ccode/MetaProfile/_load_chunked.py' \
  -WorkingDirectory 'E:/ccode/MetaProfile' -WindowStyle Hidden \
  -RedirectStandardError 'E:/ccode/MetaProfile/_load_local.err'
```

### 5.3 进度与断点续传

- 进度看 `last_id` 推进（**勿 `SELECT COUNT(*)`**，活跃写入下卡死，memory 教训）：
  ```bash
  tail -f _load_chunked.log        # 或 _load_big.log
  ```
- info_schema 近似行数（秒回，非精确）：
  ```bash
  docker exec -it mp-doris-fe mysql ... -e \
    "SELECT table_name, table_rows FROM information_schema.tables WHERE table_schema='ods_zbzx' ORDER BY table_rows DESC LIMIT 20"
  ```
- kill/换网/休眠后重启同一脚本，从 `_load_state.json`/`_load_big_state.json` 的 `last` 续。

### 5.4 校验（与云端对账）

挑几张小表全量比对：
```bash
# 云端（慢，小表才做）
python -c "import pymysql; c=pymysql.connect(host='10.242.0.1',port=9030,user='gz_kt5',password='92f5IRTld93lDPKYZZ5p',database='ods_zbzx'); cur=c.cursor(); cur.execute('SELECT TABLE_NAME,TABLE_ROWS FROM information_schema.tables WHERE TABLE_SCHEMA=\"ods_zbzx\" AND TABLE_NAME LIKE \"ods_talent%\"'); [print(r) for r in cur.fetchall()]"
# 本地
docker exec -it mp-doris-fe mysql ... -e "SELECT table_name,table_rows FROM information_schema.tables WHERE table_schema='ods_zbzx' AND table_name LIKE 'ods_talent%'"
```
小表（talent 11K / key_events 6.7K / item_category 4432）行数对齐即链路通。

---

## 6. 接入系统（DataSourceConfig + db_connections）

本地 Doris 就绪后，注册进系统（设计 §6）。建库后跑种子 SQL（实现期提供 `migrations` + seed 脚本），核心两条：

```sql
-- db_connections：两条连接
INSERT INTO db_connections (name, dialect, host, port, database, username, password_enc, pool_size, read_only, is_enabled)
VALUES
 ('ods-cloud-doris',  'doris','10.242.0.1',9030,'ods_zbzx','gz_kt5','<enc>',8,true,true),
 ('ods-local-doris',  'doris','127.0.0.1',9030,'ods_zbzx','root','<enc>',8,true,true);

-- data_source_configs：两条源（config_json 见设计 §6.2）
INSERT INTO data_source_configs (name, source_type, profile_type, config_json, schedule_cron, is_enabled)
VALUES
 ('ODS-本地-Doris','sql_warehouse','all','{"db_connection_id":<本地id>, "mode":"both", ...}', '0 2 * * *', true),
 ('ODS-云-Doris',  'sql_warehouse','all','{"db_connection_id":<云id>,   "mode":"structured_only", ...}', NULL, true);
```
默认本地源挂 cron（每日 02:00 增量），云源手动兜底。提取器读本地（快）。

---

## 7. 日常运维

| 操作 | 命令 |
|---|---|
| 启 | `cd docker/doris && docker compose up -d` |
| 停 | `docker compose down`（保留数据） |
| 看状态 | `docker compose ps` + `docker exec mp-doris-fe mysql ... -e "SHOW FRONTENDS\G; SHOW BACKENDS\G"` |
| FE Web UI | 浏览器 `http://127.0.0.1:8030`（root/无密码或你设的） |
| BE Web UI | `http://127.0.0.1:8040` |
| 看日志 | `docker logs --tail 100 mp-doris-fe` / `mp-doris-be` |
| 进容器排查 | `docker exec -it mp-doris-fe bash` / `mp-doris-be bash` |
| 备份 meta | 停 FE → 复制 `H:/docker/doris/fe/doris-meta` → 起 FE |
| 扩盘 | BE `storage_root_path` 可配多盘；本地单盘够 P1+P2 |
| 重建（清空） | `docker compose down -v` + 删 `H:/docker/doris/{fe,be}` 下内容 + §3 重来 |
| 改 BE 内存 | 编辑 `be.conf` `mem_limit` → `docker compose up -d --force-recreate doris-be` |

---

## 8. 容量与性能预期

- **结构化主表 P1 ~126GB**：WAN 2.4MB/s ≈ **15-18h**（TUN 必关）。
- **company_basic_info 429M 行 ~304GB**：~36h；建议 chunked + Stream Load。
- **附件 1.1TB**：暂不全同步，画像管线按 `content_mine_filter` 按需拉（设计 §6.2）。
- **本地读速**：建好后 BE 本地盘，全表扫远快于云 WAN（瓶颈消除）。
- **H 盘**：884GB 可用 → P1+P2（~430GB）够；附件全量需另挂盘或择表。

---

## 9. 排错（常见坑）

| 现象 | 原因 / 处理 |
|---|---|
| `SHOW BACKENDS` Alive=false | BE 没起 / priority_networks 没生效。`docker logs mp-doris-be` 看；确认 `be.conf` 挂载生效、`BE_ADDR=172.28.80.20:9050` 与 FE ADD 的地址一致。 |
| 宿主连 9030 拒绝 | FE 没起好（等 30s）或端口冲突。`netstat -ano \| findstr 9030`；若 mp-mysql 占用，停它或改映射（如 `127.0.0.1:9130:9030`，同步改 loader/PY DSN）。 |
| 建表报 `Failed to find enough host with storage medium` | 副本数 > BE 数。确认 `_doris_ddl_sync.py` 把 `replication_allocation` 改成 `: 1` 了（检查 `_doris_local_schema.sql`）。 |
| 同步极慢（40KB/s） | **Clash TUN 开着**。关 TUN，System Proxy 保留。重测 `SELECT * FROM ods_science_literature LIMIT 5000`（<10s=通）。 |
| 云端大表 SELECT OOM (`FullGC`) | 全表扫吃云端 BE 内存。用 `_load_chunked_big.py` COUNT 二分 id 窗，禁全表 `SELECT *` / `ORDER BY id` 无 LIMIT。 |
| 中文乱码（终端） | 仅 Windows 终端 cp936 显示问题，存储是 utf8mb4 无损。脚本写文件/入库带 `charset=utf8mb4` 即可。 |
| pymysql UnicodeDecodeError | 网页抓取表脏字节。memory `ods-mirror-mysql`：pymysql 已 patch `decode(replace)`，重装需重打 patch。 |
| `docker compose` 命令不存在 | 旧版 Docker Desktop 用 `docker-compose`（带横杠）。 |
| BE OOM（本地） | `be.conf` `mem_limit` 调小（如 4g），或加 swap；单副本 dev 够用。 |
| Loader 续传丢进度 | Doris 无 INSERT IGNORE，改"DELETE 窗口再 INSERT"续传；`_load_*_state.json` 的 `last` 是真续传点，勿手动改。 |

---

## 10. 一键清单（顺序执行）

```bash
# 0. 前置：TUN 关，Docker 起，H 盘够
# 1. 写 docker/doris/{docker-compose.yml,fe.conf,be.conf}（见 §2）
mkdir -p /h/docker/doris/fe/doris-meta /h/docker/doris/fe/log /h/docker/doris/be/storage /h/docker/doris/be/log
cd /e/ccode/MetaProfile/docker/doris
docker compose pull && docker compose up -d
# 2. 等 FE 起来，加 BE（§3 步4）
docker exec -it mp-doris-fe mysql -h 127.0.0.1 -P 9030 -u root -e "ALTER SYSTEM ADD BACKEND '172.28.80.20:9050'; SHOW BACKENDS\G"
# 3. 建库
docker exec -it mp-doris-fe mysql -h 127.0.0.1 -P 9030 -u root -e "CREATE DATABASE IF NOT EXISTS ods_zbzx;"
# 4. 同步 DDL
cd /e/ccode/MetaProfile && python _doris_ddl_sync.py --apply
# 5. 改 loader 目标到本地 Doris（§5.2），启 P1 同步
# 6. 验证 + 接入系统（§5.4 + §6）
```

完成后：本地 Doris 可读 → 画像抽取管线（设计文档）读本地源快速跑。
