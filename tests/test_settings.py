from __future__ import annotations

import pytest

from habr_tech_radar.settings import Settings


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HTR_LOG_LEVEL", raising=False)
    monkeypatch.delenv("HTR_DRY_RUN", raising=False)
    monkeypatch.delenv("HTR_DEMO_MODE", raising=False)
    s = Settings()
    assert s.log_level == "INFO"
    assert s.dry_run is True
    assert s.demo_mode is False


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTR_LOG_LEVEL", "debug")
    monkeypatch.setenv("HTR_DRY_RUN", "false")
    monkeypatch.setenv("HTR_DEMO_MODE", "true")
    s = Settings()
    assert s.log_level == "DEBUG"
    assert s.dry_run is False
    assert s.demo_mode is True
