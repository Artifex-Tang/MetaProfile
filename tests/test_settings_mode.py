"""settings.mode flag 测试(full/readonly)。"""
from metaprofile.shared.config.settings import Settings


def test_mode_defaults_to_full():
    s = Settings()
    assert s.mode == "full"


def test_mode_readonly_from_env(monkeypatch):
    monkeypatch.setenv("MODE", "readonly")
    s = Settings()
    assert s.mode == "readonly"
