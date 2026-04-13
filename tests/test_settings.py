from __future__ import annotations

import pytest

from habr_tech_radar.settings import Settings, parse_comma_separated_list


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTR_LOG_LEVEL", "INFO")
    monkeypatch.setenv("HTR_DRY_RUN", "true")
    monkeypatch.setenv("HTR_DEMO_MODE", "false")
    monkeypatch.setenv("HTR_PRESET_ENABLED", "false")
    s = Settings()
    assert s.log_level == "INFO"
    assert s.dry_run is True
    assert s.demo_mode is False
    assert s.max_selected_articles == 7


def test_telegram_format_mode_accepts_aliases(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTR_TELEGRAM_FORMAT_MODE", "DEBUG")
    assert Settings().telegram_format_mode == "debug"
    monkeypatch.setenv("HTR_TELEGRAM_FORMAT_MODE", "production")
    assert Settings().telegram_format_mode == "prod"


def test_settings_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTR_LOG_LEVEL", "debug")
    monkeypatch.setenv("HTR_DRY_RUN", "false")
    monkeypatch.setenv("HTR_DEMO_MODE", "true")
    s = Settings()
    assert s.log_level == "DEBUG"
    assert s.dry_run is False
    assert s.demo_mode is True


def test_parse_comma_separated_list_splits_and_strips() -> None:
    assert parse_comma_separated_list("python, asyncio , rust") == [
        "python",
        "asyncio",
        "rust",
    ]
    assert parse_comma_separated_list("") == []
    assert parse_comma_separated_list("  single  ") == ["single"]


def test_settings_keyword_lists_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTR_INCLUDE_KEYWORDS", "alpha, beta")
    monkeypatch.setenv("HTR_EXCLUDE_HUBS", "hub_a hub_b")
    monkeypatch.setenv("HTR_MAX_SELECTED_ARTICLES", "3")
    s = Settings()
    assert parse_comma_separated_list(s.include_keywords) == ["alpha", "beta"]
    assert parse_comma_separated_list(s.exclude_hubs) == ["hub_a", "hub_b"]
    assert s.max_selected_articles == 3
