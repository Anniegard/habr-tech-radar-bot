from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

from habr_tech_radar.settings import Settings, effective_last_run_path


def _parse_iso_utc(s: str) -> datetime | None:
    try:
        raw = s.replace("Z", "+00:00") if s.endswith("Z") else s
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(UTC)
    except (TypeError, ValueError):
        return None


def run_health_summary(settings: Settings, *, json_output: bool) -> int:
    """Exit 0 only if last run exists, is fresh, and status is success."""
    path = effective_last_run_path(settings)
    if not path.is_file():
        print("health: last_run file missing", file=sys.stderr)
        return 1
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as e:
        print(f"health: cannot read last_run: {e}", file=sys.stderr)
        return 1
    if not isinstance(data, dict):
        print("health: last_run root must be an object", file=sys.stderr)
        return 1

    status = data.get("status")
    finished_raw = data.get("finished_at_utc")
    if not isinstance(finished_raw, str):
        print("health: invalid finished_at_utc", file=sys.stderr)
        return 1
    finished = _parse_iso_utc(finished_raw)
    if finished is None:
        print("health: cannot parse finished_at_utc", file=sys.stderr)
        return 1

    age_minutes = (datetime.now(UTC) - finished).total_seconds() / 60.0
    max_age = float(settings.health_max_age_minutes)
    stale = age_minutes > max_age

    if status != "success" or stale:
        if json_output:
            out = {**data, "health_ok": False, "stale": stale, "age_minutes": age_minutes}
            print(json.dumps(out, ensure_ascii=False))
        else:
            print(
                f"status={status} run_id={data.get('run_id')} finished_at={finished_raw} "
                f"age_minutes={age_minutes:.1f} max_age_minutes={max_age} stale={stale}",
                file=sys.stderr,
            )
        return 1

    if json_output:
        out = {**data, "health_ok": True, "stale": False, "age_minutes": age_minutes}
        print(json.dumps(out, ensure_ascii=False))
    else:
        print(
            "status=success "
            f"run_id={data.get('run_id')} "
            f"finished_at={finished_raw} "
            f"duration={data.get('duration_seconds')}s "
            f"selected={data.get('selected_count')} "
            f"sent={data.get('sent_count')} "
            f"failed={data.get('failed_count')} "
            f"skipped_due_budget={data.get('skipped_due_budget_count')}"
        )
    return 0
