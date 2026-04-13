from __future__ import annotations

import json
from pathlib import Path

import pytest

from habr_tech_radar.config.preset import apply_preset_env_overlay
from habr_tech_radar.settings import Settings


def test_preset_fills_unset_fields_from_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    preset = tmp_path / "p.json"
    preset.write_text(
        json.dumps(
            {
                "include_keywords": ["alpha", "beta"],
                "max_selected_articles": 3,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HTR_PRESET_PATH", str(preset))
    s = apply_preset_env_overlay(Settings())
    assert "alpha" in s.include_keywords
    assert s.max_selected_articles == 3


def test_preset_does_not_override_explicit_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    preset = tmp_path / "p.json"
    preset.write_text(
        json.dumps({"include_keywords": ["from_file"], "max_selected_articles": 99}),
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HTR_PRESET_PATH", str(preset))
    monkeypatch.setenv("HTR_INCLUDE_KEYWORDS", "from_env")
    s = apply_preset_env_overlay(Settings())
    assert s.include_keywords == "from_env"
    assert s.max_selected_articles == 99
