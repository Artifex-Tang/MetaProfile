"""/api/v1/runtime/flags 端点测试。"""
import pytest
from fastapi.testclient import TestClient

from metaprofile.backend.main import app


@pytest.fixture(autouse=True)
def _reset_app_mode():
    """每个测试后复原 app.state.mode,避免 readonly 污染其他测试。"""
    yield
    app.state.mode = "full"


def test_runtime_flags_returns_mode():
    app.state.mode = "readonly"
    r = TestClient(app).get("/api/v1/runtime/flags")
    assert r.status_code == 200
    assert r.json()["mode"] == "readonly"


def test_runtime_flags_not_blocked_in_readonly():
    """runtime/flags 必须在 readonly 下可访问(前端读它隐藏菜单)。"""
    app.state.mode = "readonly"
    r = TestClient(app).get("/api/v1/runtime/flags")
    assert r.status_code == 200
