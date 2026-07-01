"""readonly_guard middleware 测试。"""
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from metaprofile.backend.readonly_guard import BLOCKED_PREFIXES, readonly_guard


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

    @app.post("/api/v1/profile/org/search")
    def search_org():
        return {"items": []}

    @app.post("/api/v1/profile/org/import")
    def import_org():
        return {"task_id": 1}

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


def test_readonly_allows_profile_search_post():
    """POST /profile/search 是读操作,应通(非 503)。"""
    client = TestClient(_app("readonly"))
    assert client.post("/api/v1/profile/org/search").status_code == 200


def test_readonly_blocks_profile_import_post():
    """POST /profile/import 是写操作,应 503。"""
    client = TestClient(_app("readonly"))
    assert client.post("/api/v1/profile/org/import").status_code == 503


@pytest.mark.parametrize("prefix", list(BLOCKED_PREFIXES))
def test_every_blocked_prefix_returns_503(prefix):
    client = TestClient(_app("readonly"))
    r = client.get(prefix)
    assert r.status_code == 503
