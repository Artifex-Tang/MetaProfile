from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from metaprofile.new_tech_discovery.api.routes_new_tech import get_db
from metaprofile.new_tech_discovery.main import app


def test_trigger_scan_enqueues_celery_task():
    # 无需真实 DB：覆盖 get_db 依赖避免 open session（Celery 分支用不到 db）。
    async def _fake_db():
        yield None

    app.dependency_overrides[get_db] = _fake_db
    try:
        client = TestClient(app)
        with patch(
            "metaprofile.new_tech_discovery.api.routes_new_tech.extract_weak_signals"
        ) as task_mock:
            task_mock.delay = MagicMock(return_value=MagicMock(id="fake-id"))
            resp = client.post("/api/v1/new-tech/scan?db_connection_id=4")
    finally:
        app.dependency_overrides.pop(get_db, None)

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "queued"
    assert body["task_id"] == "fake-id"
    task_mock.delay.assert_called_once()
