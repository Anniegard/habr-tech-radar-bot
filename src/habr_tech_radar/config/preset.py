from __future__ import annotations

import json
import logging
from importlib import resources
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from habr_tech_radar.settings import Settings

logger = logging.getLogger(__name__)


class RadarPreset(BaseModel):
    """Optional JSON preset; lists as arrays of strings."""

    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    include_hubs: list[str] = Field(default_factory=list)
    exclude_hubs: list[str] = Field(default_factory=list)
    max_selected_articles: int | None = None


def _preset_path_resolved(settings: Settings) -> Path:
    p = settings.preset_path
    if p.is_absolute():
        return p.resolve()
    if settings.project_root is not None:
        return (settings.project_root / p).resolve()
    return (Path.cwd() / p).resolve()


def _parse_preset_json(raw: str, *, source: str) -> RadarPreset | None:
    try:
        data: Any = json.loads(raw)
    except json.JSONDecodeError as e:
        logger.warning("config: could not parse preset JSON %s: %s", source, e)
        return None
    if not isinstance(data, dict):
        logger.warning("config: preset root must be an object: %s", source)
        return None
    try:
        return RadarPreset.model_validate(data)
    except Exception as e:  # noqa: BLE001
        logger.warning("config: invalid preset schema %s: %s", source, e)
        return None


def load_radar_preset(path: Path) -> RadarPreset | None:
    if path.is_file():
        try:
            raw = path.read_text(encoding="utf-8")
        except OSError as e:
            logger.warning("config: could not read preset %s: %s", path, e)
            return None
        return _parse_preset_json(raw, source=str(path))

    # Fallback: packaged default when repo `config/` is not present (editable installs).
    try:
        ref = resources.files("habr_tech_radar.config").joinpath("default_radar.json")
        raw_pkg = ref.read_text(encoding="utf-8")
    except (OSError, FileNotFoundError, TypeError, ValueError) as e:
        logger.warning("config: preset missing %s and packaged fallback failed: %s", path, e)
        return None
    p = _parse_preset_json(raw_pkg, source="habr_tech_radar.config.default_radar.json")
    if p is not None:
        logger.info("config: using packaged default preset (path not found: %s)", path)
    return p


def _join_terms(terms: list[str]) -> str:
    return ", ".join(t.strip() for t in terms if t and str(t).strip())


def apply_preset_env_overlay(settings: Settings) -> Settings:
    """Apply JSON preset only for fields not set via env / .env (pydantic model_fields_set)."""
    if not settings.preset_enabled:
        return settings
    path = _preset_path_resolved(settings)
    preset = load_radar_preset(path)
    if preset is None:
        return settings

    explicit = settings.model_fields_set
    updates: dict[str, Any] = {}

    if "include_keywords" not in explicit and preset.include_keywords:
        updates["include_keywords"] = _join_terms(preset.include_keywords)
    if "exclude_keywords" not in explicit and preset.exclude_keywords:
        updates["exclude_keywords"] = _join_terms(preset.exclude_keywords)
    if "include_hubs" not in explicit and preset.include_hubs:
        updates["include_hubs"] = _join_terms(preset.include_hubs)
    if "exclude_hubs" not in explicit and preset.exclude_hubs:
        updates["exclude_hubs"] = _join_terms(preset.exclude_hubs)
    if "max_selected_articles" not in explicit and preset.max_selected_articles is not None:
        updates["max_selected_articles"] = preset.max_selected_articles

    if not updates:
        return settings
    merged = settings.model_copy(update=updates)
    logger.info(
        "config: applied preset %s (non-overridden fields only): %s",
        path,
        ", ".join(sorted(updates.keys())),
    )
    return merged
