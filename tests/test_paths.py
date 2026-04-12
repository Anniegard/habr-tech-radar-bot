from __future__ import annotations

from pathlib import Path

import pytest

from habr_tech_radar.delivery.http_telegram import TelegramDeliveryError
from habr_tech_radar.main import main
from habr_tech_radar.settings import Settings, effective_state_file


def test_effective_state_file_absolute(tmp_path: Path) -> None:
    p = tmp_path / "state.json"
    s = Settings(state_file=p)
    assert effective_state_file(s) == p.resolve()


def test_effective_state_file_relative_to_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    s = Settings(state_file=Path(".habr_tech_radar_seen.json"))
    assert effective_state_file(s) == (tmp_path / ".habr_tech_radar_seen.json").resolve()


def test_effective_state_file_relative_to_project_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "app"
    root.mkdir()
    monkeypatch.chdir(tmp_path)
    s = Settings(state_file=Path("var/seen.json"), project_root=root)
    assert effective_state_file(s) == (root / "var" / "seen.json").resolve()


def test_main_returns_2_when_live_telegram_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTR_DRY_RUN", "false")
    monkeypatch.delenv("HTR_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("HTR_TELEGRAM_CHAT_ID", raising=False)
    monkeypatch.setenv("HTR_DEMO_MODE", "true")
    assert main([]) == 2


def test_main_returns_1_on_telegram_delivery_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTR_DRY_RUN", "false")
    monkeypatch.setenv("HTR_TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("HTR_TELEGRAM_CHAT_ID", "1")
    monkeypatch.setenv("HTR_DEMO_MODE", "true")

    def boom(_components: object) -> None:
        raise TelegramDeliveryError("Telegram delivery incomplete: failed=1 sent=0 selected=1")

    monkeypatch.setattr("habr_tech_radar.main.run_pipeline", boom)
    assert main([]) == 1
