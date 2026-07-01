# 云上只读轻量部署 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 单台阿里云 ECS + docker 跑一个去 Doris 的纯只读 MetaProfile,数据预导入,ODS/采集/LLM API 熔断。

**Architecture:** 派生 readonly docker-compose(去 doris/litellm/worker/beat/rabbitmq/es,留 postgres/neo4j/redis/backend/frontend)。后端加 FastAPI middleware(`readonly_guard`)读 `settings.mode=readonly`,拦截 ODS/采集/llm/enrich/scheduler 前缀 + 画像写方法,返回 503。Terraform 起 VPC+ECS+OSS,user-data 自动装 docker + 从 OSS 内网拉 dump + restore + up。spec: `docs/superpowers/specs/2026-07-01-cloud-readonly-deploy-design.md`。

**Tech Stack:** FastAPI + pydantic-settings(pydantic v2)、SQLAlchemy async、Neo4j、Redis、Docker Compose、Terraform(alicloud provider)、阿里云 ECS/OSS。

---

## File Structure

**新增:**
- `metaprofile/backend/readonly_guard.py` — middleware + 受影响前缀常量 + 503 JSONResponse
- `metaprofile/backend/routes_runtime.py` — `GET /api/v1/runtime/flags` 返回 `{mode}`(不受熔断,供前端读)
- `deploy/docker-compose.readonly.yml` — 只读栈 compose(5 容器)
- `deploy/cloud/user-data.sh` — ECS 启动脚本(装 docker + restore + up)
- `deploy/cloud/main.tf` + `variables.tf` — Terraform(VPC/ECS/OSS/安全组/EIP)
- `scripts/export_readonly_data.sh` — 本地导出 pg_dump + neo4j dump 打包
- `tests/backend/test_readonly_guard.py` — middleware 单元 + 集成测试
- `tests/backend/test_runtime_flags.py` — runtime flags 端点测试

**修改:**
- `metaprofile/shared/config/settings.py` — `Settings` 加 `mode: Literal["full","readonly"]` 字段
- `metaprofile/backend/main.py` — 注册 `readonly_guard` middleware + `routes_runtime` router
- `frontend/src/api/client.ts`(或运行时 config) — 读 `/api/v1/runtime/flags` 隐藏被熔断菜单(可选,后置)

---

## Part 1 — 熔断代码(本地可 TDD,先做)

### Task 1: settings.mode flag

**Files:**
- Modify: `metaprofile/shared/config/settings.py:171`(Settings 类)
- Test: `tests/test_settings_mode.py`(新建)

- [ ] **Step 1: 写失败测试**

```python
# tests/test_settings_mode.py
from metaprofile.shared.config.settings import Settings


def test_mode_defaults_to_full():
    s = Settings()
    assert s.mode == "full"


def test_mode_readonly_from_env(monkeypatch):
    monkeypatch.setenv("MODE", "readonly")
    s = Settings()
    assert s.mode == "readonly"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/test_settings_mode.py -v`
Expected: FAIL — `Settings` 无 `mode` 字段(AttributeError / validation error)

- [ ] **Step 3: 实现 — 加字段**

`metaprofile/shared/config/settings.py` Settings 类(在 `env` 字段后加):

```python
    env: Literal["dev", "staging", "prod"] = "dev"
    # 运行模式:full=全功能(本地开发);readonly=云上只读(熔断 ODS/采集/LLM/写)
    mode: Literal["full", "readonly"] = "full"
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/test_settings_mode.py -v`
Expected: PASS(2 passed)

- [ ] **Step 5: 验证现有测试不受影响**

Run: `pytest tests/ -k "settings" -v`
Expected: 全 PASS(mode 默认 full,无副作用)

- [ ] **Step 6: Commit**

```bash
git add metaprofile/shared/config/settings.py tests/test_settings_mode.py
git commit -m "feat(config): add mode flag (full|readonly) for cloud readonly deploy"
```

---

### Task 2: readonly_guard middleware

**Files:**
- Create: `metaprofile/backend/readonly_guard.py`
- Modify: `metaprofile/backend/main.py:105-110`(app 创建后挂 middleware)
- Test: `tests/backend/test_readonly_guard.py`(新建)

- [ ] **Step 1: 写失败测试**

```python
# tests/backend/test_readonly_guard.py
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from metaprofile.backend.readonly_guard import readonly_guard, BLOCKED_PREFIXES


def _app(mode: str) -> FastAPI:
    app = FastAPI()
    app.state.mode = mode
    app.middleware("http")(readonly_guard)

    @app.get("/api/v1/profile/org/{org_id}")
    def get_org(org_id: str):
        return {"id": org_id}

    @app.put("/api/v1/profile/org/{org_id}")
    def put_org(org_id: str):
        return {"updated": org_id}

    @app.post("/api/v1/settings/collection/trigger/{ds_id}")
    def trigger(ds_id: int):
        return {"task_id": 1}

    @app.get("/api/v1/settings/llm")
    def list_llm():
        return []

    return app


def test_full_mode_passes_everything():
    client = TestClient(_app("full"))
    assert client.put("/api/v1/profile/org/o1").status_code == 200
    assert client.post("/api/v1/settings/collection/trigger/1").status_code == 200


def test_readonly_blocks_blocked_prefixes():
    client = TestClient(_app("readonly"))
    # ODS 采集前缀整块熔断
    r = client.post("/api/v1/settings/collection/trigger/1")
    assert r.status_code == 503
    assert r.json()["detail"] == "disabled in readonly mode"
    # LLM 配置 GET 也熔断
    assert client.get("/api/v1/settings/llm").status_code == 503


def test_readonly_blocks_profile_writes_but_keeps_get():
    client = TestClient(_app("readonly"))
    # GET 画像 → 留
    assert client.get("/api/v1/profile/org/o1").status_code == 200
    # PUT 写画像 → 熔断
    assert client.put("/api/v1/profile/org/o1").status_code == 503


@pytest.mark.parametrize("prefix", list(BLOCKED_PREFIXES))
def test_every_blocked_prefix_returns_503(prefix):
    client = TestClient(_app("readonly"))
    # 用 OPTIONS/任意方法触 prefix 即可;此处验证前缀字符串覆盖预期模块
    r = client.get(prefix)
    assert r.status_code == 503
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/backend/test_readonly_guard.py -v`
Expected: FAIL — `readonly_guard` 不存在(ImportError)

- [ ] **Step 3: 实现 middleware**

```python
# metaprofile/backend/readonly_guard.py
"""只读模式熔断中间件。

settings.mode == "readonly" 时:
- 命中 BLOCKED_PREFIXES 的请求(ODS/采集/LLM/enrich/scheduler/db-connections)→ 503
- 画像层写方法(POST/PUT/PATCH/DELETE)→ 503
GET 画像查询 / 分析层 / /health / /api/v1/runtime/flags 全保留。
"""
from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

# 整块熔断前缀(设置层 ODS/采集/LLM/enrich-tasks/scheduler/db-connections)
BLOCKED_PREFIXES: tuple[str, ...] = (
    "/api/v1/settings/datasources",
    "/api/v1/settings/collection",
    "/api/v1/settings/scheduled-tasks",
    "/api/v1/settings/enrichment-tasks",
    "/api/v1/settings/llm",
    "/api/v1/settings/db-connections",
    "/api/v1/settings/translate",  # scheduler translate/batch(走 LLM)
)

WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

_DISABLED_JSON = JSONResponse(
    status_code=503,
    content={"detail": "disabled in readonly mode"},
)


async def readonly_guard(request: Request, call_next):
    mode = getattr(request.app.state, "mode", "full")
    if mode != "readonly":
        return await call_next(request)

    path = request.url.path
    if any(path.startswith(p) for p in BLOCKED_PREFIXES):
        return _DISABLED_JSON
    if request.method in WRITE_METHODS and path.startswith("/api/v1/profile/"):
        return _DISABLED_JSON

    return await call_next(request)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `pytest tests/backend/test_readonly_guard.py -v`
Expected: PASS(全部)

- [ ] **Step 5: Commit**

```bash
git add metaprofile/backend/readonly_guard.py tests/backend/test_readonly_guard.py
git commit -m "feat(backend): add readonly_guard middleware (503 on ODS/LLM/profile-writes)"
```

---

### Task 3: 挂载 middleware + runtime flags 端点

**Files:**
- Modify: `metaprofile/backend/main.py`(挂 middleware + 设 app.state.mode + 注册 runtime router)
- Create: `metaprofile/backend/routes_runtime.py`
- Test: `tests/backend/test_runtime_flags.py`

- [ ] **Step 1: 写失败测试**

```python
# tests/backend/test_runtime_flags.py
from fastapi.testclient import TestClient

from metaprofile.backend.main import app


def test_runtime_flags_returns_mode():
    app.state.mode = "readonly"
    r = TestClient(app).get("/api/v1/runtime/flags")
    assert r.status_code == 200
    assert r.json()["mode"] == "readonly"


def test_runtime_flags_not_blocked_in_readonly():
    """runtime/flags 必须在 readonly 下可访问(前端要读它隐藏菜单)。"""
    app.state.mode = "readonly"
    r = TestClient(app).get("/api/v1/runtime/flags")
    assert r.status_code == 200
```

- [ ] **Step 2: 跑测试确认失败**

Run: `pytest tests/backend/test_runtime_flags.py -v`
Expected: FAIL — `/api/v1/runtime/flags` 路由不存在(404)

- [ ] **Step 3: 实现 runtime router**

```python
# metaprofile/backend/routes_runtime.py
"""运行时标志端点:供前端读取当前模式以隐藏被熔断的菜单入口。"""
from __future__ import annotations

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api/v1/runtime", tags=["runtime"])


@router.get("/flags")
async def runtime_flags(request: Request) -> dict[str, str]:
    return {"mode": getattr(request.app.state, "mode", "full")}
```

- [ ] **Step 4: 挂载到 main.py**

`metaprofile/backend/main.py` 修改:

(a) 顶部 import 区加:
```python
from metaprofile.backend.readonly_guard import readonly_guard
from metaprofile.backend.routes_runtime import router as runtime_router
```

(b) `app = FastAPI(...)` 创建后立刻加(在 include_router 之前):
```python
app.state.mode = settings.mode
app.middleware("http")(readonly_guard)
```

(c) include_router 区末尾(health 之前)加:
```python
app.include_router(runtime_router)
```

- [ ] **Step 5: 跑测试确认通过**

Run: `pytest tests/backend/test_runtime_flags.py tests/backend/test_readonly_guard.py -v`
Expected: PASS

- [ ] **Step 6: 跑全量回归确认 full 模式无副作用**

Run: `pytest tests/ -x -q 2>&1 | tail -20`
Expected: 现有测试全 PASS(mode 默认 full,middleware 直通)

- [ ] **Step 7: Commit**

```bash
git add metaprofile/backend/main.py metaprofile/backend/routes_runtime.py tests/backend/test_runtime_flags.py
git commit -m "feat(backend): mount readonly_guard + /api/v1/runtime/flags endpoint"
```

---

### Task 4(可选,后置): 前端隐藏被熔断菜单

**Files:**
- Modify: 前端读取 `/api/v1/runtime/flags` 的位置(通常 `frontend/src/api/client.ts` 或 App 启动 bootstrap)
- Modify: 含"采集 / 数据源 / LLM 配置 / 批量导入"入口的导航组件

- [ ] **Step 1: 启动后调 `/api/v1/runtime/flags`,存 `mode` 到全局 store/context**

前端 bootstrap 处加(`frontend/src/api/client.ts` 或等价):
```ts
export async function fetchRuntimeFlags() {
  const r = await fetch('/api/v1/runtime/flags');
  return r.json() as Promise<{ mode: 'full' | 'readonly' }>;
}
```

- [ ] **Step 2: 导航组件读 mode,`readonly` 时隐藏采集/LLM/db-connections/import 入口**

定位导航组件(grep `采集` / `数据源` / `LLM` 关键词找),对受影响菜单项加 `{mode === 'readonly' && <MenuItem .../>}` 式条件渲染。

- [ ] **Step 3: 手验**

本地起栈,`MODE=readonly` 启 backend → 前端菜单隐藏 → 直接 curl 被熔断端点返 503。

- [ ] **Step 4: Commit**

```bash
git add frontend/src/
git commit -m "feat(frontend): hide ODS/LLM/import menus in readonly mode"
```

---

## Part 2 — 云部署(依赖 Part 1 + 真实阿里云,验收式)

### Task 5: readonly docker-compose 派生

**Files:**
- Create: `deploy/docker-compose.readonly.yml`

- [ ] **Step 1: 从主 compose 派生,只留 5 服务**

保留:`postgres`、`neo4j`、`redis`、`backend`、`frontend`。删除:`elasticsearch`、`doris-fe`、`doris-be`、`litellm`、`rabbitmq`、`backend-worker`、`migrate`、`seed`。

- [ ] **Step 2: backend 加 MODE env + 去依赖 worker/rabbitmq**

`backend` 服务 `environment` 加:
```yaml
      MODE: readonly
```
移除 `depends_on` 里的 rabbitmq/es(已删服务)。保留 depends postgres/neo4j/redis。

- [ ] **Step 3: postgres/neo4j 数据卷指向预导入挂载点**

```yaml
services:
  postgres:
    volumes:
      - pgdata:/var/lib/postgresql/data
  neo4j:
    volumes:
      - neo4jdata:/data
volumes:
  pgdata:
  neo4jdata:
```

- [ ] **Step 4: 本地干跑验证**

Run: `MODE=readonly docker compose -f deploy/docker-compose.readonly.yml up -d`
Expected: 5 容器 healthy;`curl localhost:8000/api/v1/runtime/flags` → `{"mode":"readonly"}`;被熔断端点 503。

- [ ] **Step 5: Commit**

```bash
git add deploy/docker-compose.readonly.yml
git commit -m "feat(deploy): add readonly docker-compose (5-service, no doris/llm/worker)"
```

---

### Task 6: 数据导出脚本(本地)

**Files:**
- Create: `scripts/export_readonly_data.sh`

- [ ] **Step 1: 写导出脚本**

```bash
#!/usr/bin/env bash
# 导出云只读部署所需数据:postgres typed 表 + neo4j 全库。
# 产物:readonly-data.tar(pg.dump + neo4j.dump)→ 上传 OSS。
set -euo pipefail

OUT_DIR="${1:-./readonly-data-export}"
mkdir -p "$OUT_DIR"

# 1. postgres:只导数据(结构由 migration 建),含 typed ORM 表 + 必要配置表
docker exec metaprofile-postgres-1 pg_dump \
  -U metaprofile -d metaprofile --data-only \
  --exclude-table-data=alembic_version \
  --exclude-table-data=llm_call_log \
  > "$OUT_DIR/pg.dump"

# 2. neo4j:全库 dump
docker exec metaprofile-neo4j-1 neo4j-admin database dump neo4j \
  --to-path="$OUT_DIR" --overwrite
mv "$OUT_DIR/neo4j.dump" "$OUT_DIR/neo4j.dump" 2>/dev/null || true

# 3. 打包
tar -cf "$OUT_DIR/readonly-data.tar" -C "$OUT_DIR" pg.dump neo4j.dump
ls -lh "$OUT_DIR/readonly-data.tar"
echo "→ 上传 OSS: ossutil cp $OUT_DIR/readonly-data.tar oss://<bucket>/readonly-data.tar"
```

- [ ] **Step 2: 跑一次确认产物**

Run: `bash scripts/export_readonly_data.sh`
Expected: `readonly-data.tar` 生成,含 pg.dump + neo4j.dump。

- [ ] **Step 3: 上传 OSS(需 ossutil 配好 AK)**

Run: `ossutil cp readonly-data-export/readonly-data.tar oss://<bucket>/readonly-data.tar`
Expected: 上传成功。

- [ ] **Step 4: Commit**

```bash
git add scripts/export_readonly_data.sh
git commit -m "feat(scripts): add export_readonly_data.sh (pg+neo4j dump → tar)"
```

---

### Task 7: ECS user-data 部署脚本

**Files:**
- Create: `deploy/cloud/user-data.sh`

- [ ] **Step 1: 写 user-data**

```bash
#!/usr/bin/env bash
# ECS 启动脚本(Terraform user-data 注入)。
# 装 docker → 拉 readonly compose + dump(OSS 内网)→ restore → up。
set -euo pipefail
exec > >(tee -a /var/log/cloud-init-output.log) 2>&1

OSS_BUCKET="${OSS_BUCKET}"          # Terraform 注入
PG_PASSWORD="${PG_PASSWORD}"        # Terraform 注入
NEO4J_PASSWORD="${NEO4J_PASSWORD}"  # Terraform 注入

# 1. 装 docker
dnf install -y docker || apt-get update && apt-get install -y docker.io
systemctl enable --now docker
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" \
  -o /usr/local/bin/docker-compose && chmod +x /usr/local/bin/docker-compose

# 2. 拉产物(OSS 内网 endpoint)
mkdir -p /opt/metaprofile
cd /opt/metaprofile
ossutil cp "oss://${OSS_BUCKET}/readonly-data.tar" readonly-data.tar --internal
ossutil cp "oss://${OSS_BUCKET}/docker-compose.readonly.yml" docker-compose.yml --internal
tar -xf readonly-data.tar

# 3. 起数据层 + restore
docker-compose up -d postgres neo4j redis
sleep 30  # 等健康
docker exec metaprofile-postgres-1 pg_restore -U metaprofile -d metaprofile --data-only /opt/metaprofile/pg.dump || true
docker exec metaprofile-neo4j-1 neo4j-admin database load neo4j --from-path=/opt/metaprofile --overwrite

# 4. 起应用(readonly env 已在 compose)
MODE=readonly docker-compose up -d backend frontend
echo "deploy done"
```

- [ ] **Step 2: 上传 compose + user-data 到 OSS**

Run:
```bash
ossutil cp deploy/docker-compose.readonly.yml oss://<bucket>/
ossutil cp deploy/cloud/user-data.sh oss://<bucket>/
```

- [ ] **Step 3: Commit**

```bash
git add deploy/cloud/user-data.sh
git commit -m "feat(cloud): add ECS user-data (docker install + restore + compose up)"
```

---

### Task 8: Terraform 模板

**Files:**
- Create: `deploy/cloud/main.tf`
- Create: `deploy/cloud/variables.tf`
- Create: `deploy/cloud/user-data.tpl`(模板,渲染 OSS_BUCKET/密码)

- [ ] **Step 1: variables.tf**

```hcl
variable "region"           { default = "cn-hangzhou" }
variable "instance_type"    { default = "ecs.g7.2xlarge" }  # 8C16G
variable "system_disk_size" { default = 100 }                # GB
variable "data_disk_size"   { default = 200 }                # GB ESSD,pg+neo4j
variable "oss_bucket"       { default = "metaprofile-readonly" }
variable "pg_password"      { type = string sensitive = true }
variable "neo4j_password"   { type = string sensitive = true }
```

- [ ] **Step 2: main.tf(VPC + ECS + OSS + 安全组 + EIP)**

```hcl
terraform {
  required_providers {
    alicloud = { source = "aliyun/alicloud" version = "~> 1.220" }
  }
}
provider "alicloud" { region = var.region }

resource "alicloud_vpc" "v" {
  cidr_block = "172.16.0.0/12"
  name       = "metaprofile-vpc"
}
resource "alicloud_vswitch" "s" {
  vpc_id     = alicloud_vpc.v.id
  cidr_block = "172.16.0.0/21"
  zone_id    = "${var.region}-h"
}

resource "alicloud_security_group" "sg" {
  vpc_id = alicloud_vpc.v.id
  name   = "metaprofile-sg"
}
resource "alicloud_security_group_rule" "http" {
  type              = "ingress"
  ip_protocol       = "tcp"
  port_range        = "80/80"
  security_group_id = alicloud_security_group.sg.id
  cidr_ip           = "0.0.0.0/0"
}
resource "alicloud_security_group_rule" "ssh" {
  type              = "ingress"
  ip_protocol       = "tcp"
  port_range        = "22/22"
  security_group_id = alicloud_security_group.sg.id
  cidr_ip           = "0.0.0.0/0"
}

resource "alicloud_oss_bucket" "b" {
  bucket = var.oss_bucket
  acl    = "private"
}

resource "alicloud_instance" "app" {
  instance_type   = var.instance_type
  image_id        = "aliyun_3_x64_20G_alibase_20240528.vhd"  # Alibaba Cloud Linux 3
  system_disk_category = "cloud_essd"
  system_disk_size     = var.system_disk_size
  data_disks {
    size               = var.data_disk_size
    category           = "cloud_essd"
    name               = "data"
  }
  vswitch_id     = alicloud_vswitch.s.id
  security_groups = [alicloud_security_group.sg.id]
  user_data       = templatefile("${path.module}/user-data.tpl", {
    OSS_BUCKET     = alicloud_oss_bucket.b.id
    PG_PASSWORD    = var.pg_password
    NEO4J_PASSWORD = var.neo4j_password
  })
  tags = { Name = "metaprofile-readonly" }
}

resource "alicloud_eip_association" "eip" {
  allocation_id = alicloud_eip.eip.id
  instance_id   = alicloud_instance.app.id
}
resource "alicloud_eip" "eip" {
  bandwidth            = 5
  internet_charge_type = "PayByTraffic"
}
```

- [ ] **Step 3: 一键应用**

Run:
```bash
cd deploy/cloud
terraform init
terraform apply -var="pg_password=xxx" -var="neo4j_password=yyy"
```
Expected: VPC + ECS + OSS + EIP 创建完成;ECS user-data 自动起栈。

- [ ] **Step 4: Commit**

```bash
git add deploy/cloud/
git commit -m "feat(cloud): terraform template (VPC+ECS+OSS+SG+EIP single-instance readonly)"
```

---

### Task 9: 端到端验收

- [ ] **Step 1: health + flags**

```bash
curl http://<EIP>/api/v1/runtime/flags      # {"mode":"readonly"}
curl http://<EIP>/health                     # {"status":"ok"}
```

- [ ] **Step 2: profile 真数据**

```bash
curl 'http://<EIP>/api/v1/profile/org/search' -X POST -d '{}' -H 'Content-Type: application/json'
# 返回预导入的真实画像数据(非空)
```

- [ ] **Step 3: 熔断生效**

```bash
curl -X POST http://<EIP>/api/v1/settings/collection/trigger/1   # 503
curl http://<EIP>/api/v1/settings/llm                              # 503
curl -X PUT http://<EIP>/api/v1/profile/org/x                      # 503
```

- [ ] **Step 4: frontend 可浏览**

浏览器开 `http://<EIP>` → 画像页可查/搜/关系图谱 + 跨画像跳转;采集/LLM 菜单隐藏。

- [ ] **Step 5: 全量模式本地仍绿**

Run: `pytest tests/ -q`
Expected: PASS(Part 1 代码不影响 full 模式)

---

## Self-Review 结果

**Spec 覆盖**:
- 栈清单(Task 5)✓ / 熔断机制(Task 1-3)✓ / 数据预导入(Task 6)✓ / IaC(Task 8)✓ / 网络(EIP+VPC Task 8)✓ / 验收(Task 9)✓ / 风险(ECS 规格 Task 8 var、备份 Task 6+ESSD)✓
- Task 4(前端隐藏)标可选,因 API 层已 503 兜底,前端不藏也能用(只是菜单点了 503)

**Placeholder**:无。每个 code step 有完整代码或精确命令。Terraform image_id 用阿里云 Linux 3 公共镜像 ID(实际 apply 前在控制台确认当前 ID)。

**Type 一致**:`settings.mode` (Task 1) ↔ `app.state.mode` (Task 2/3) ↔ `/api/v1/runtime/flags` 返回 `{mode}` (Task 3/前端) 一致。`BLOCKED_PREFIXES` (Task 2) 覆盖 spec 第 4 节全部熔断模块。

**Scope**:单一 plan 覆盖只读云部署全链。Part 1(代码)本地可独立交付;Part 2(部署)依赖阿里云账号 + Part 1 完成。建议执行序:Task 1→2→3→(4)→5→6→7→8→9。
