from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from metaprofile.profile_tech.main import app as tech_app
from metaprofile.settings_api.main import app as settings_app


def test_tech_translate_endpoint_enqueues():
    client = TestClient(tech_app)
    with patch("metaprofile.profile_tech.api.routes_enrichment.translate_name") as t:
        t.delay = MagicMock(return_value=MagicMock(id="abc"))
        r = client.post("/api/v1/profile/tech/T1/translate")
    assert r.status_code == 200
    assert r.json()["task_id"] == "abc"
    t.delay.assert_called_once_with("tech", "T1")


def test_settings_batch_translate_endpoint():
    client = TestClient(settings_app)
    with patch("metaprofile.settings_api.api.routes_scheduler.batch_translate_names") as t:
        t.delay = MagicMock(return_value=MagicMock(id="batch1"))
        r = client.post("/api/v1/settings/translate/batch?entity_type=tech")
    assert r.status_code == 200 and r.json()["task_id"] == "batch1"
    t.delay.assert_called_once_with("tech")


def test_settings_create_scheduled_task_validates_cron():
    client = TestClient(settings_app)
    r = client.post("/api/v1/settings/scheduled-tasks",
                    json={"name": "x", "task_type": "translate_batch",
                          "cron": "bad cron", "params": {}})
    assert r.status_code == 422
