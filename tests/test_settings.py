from __future__ import annotations

from pathlib import Path

import pytest
from pydantic_settings import SettingsConfigDict

from habr_tech_radar.settings import Settings, parse_comma_separated_list


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTR_LOG_LEVEL", "INFO")
    monkeypatch.setenv("HTR_DRY_RUN", "true")
    monkeypatch.setenv("HTR_DEMO_MODE", "false")
    s = Settings()
    assert s.log_level == "INFO"
    assert s.dry_run is True
    assert s.demo_mode is False


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


def test_env_file_layering_local_overrides_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Last env file wins; real repo uses config/defaults.env then .env."""
    monkeypatch.chdir(tmp_path)
    defaults = tmp_path / "defaults.env"
    local = tmp_path / ".env"
    defaults.write_text("HTR_LOG_LEVEL=WARNING\nHTR_MAX_SELECTED_ARTICLES=5\n", encoding="utf-8")
    local.write_text("HTR_LOG_LEVEL=ERROR\n", encoding="utf-8")

    class LayeredSettings(Settings):
        model_config = SettingsConfigDict(
            env_prefix="HTR_",
            env_file=(defaults, local),
            env_file_encoding="utf-8",
            extra="ignore",
        )

    s = LayeredSettings()
    assert s.log_level == "ERROR"
    assert s.max_selected_articles == 5


def test_environment_overrides_env_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("HTR_LOG_LEVEL=WARNING\n", encoding="utf-8")
    monkeypatch.setenv("HTR_LOG_LEVEL", "DEBUG")
    s = Settings()
    assert s.log_level == "DEBUG"


def test_hybrid_scoring_settings_defaults() -> None:
    s = Settings()
    assert s.llm_scoring_enabled is True
    assert s.llm_keyword_threshold == 20
    assert s.keyword_score_max == 50
    assert s.llm_score_max == 50
