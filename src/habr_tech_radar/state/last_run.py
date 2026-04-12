from __future__ import annotations

import contextlib
import json
import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

LastRunStatus = Literal["success", "partial", "failed", "config_error"]


@dataclass(frozen=True)
class LastRunRecord:
    run_id: str
    started_at_utc: str
    finished_at_utc: str
    duration_seconds: float
    status: LastRunStatus
    exit_code: int
    fetched_count: int
    selected_count: int
    sent_count: int
    failed_count: int
    skipped_due_budget_count: int
    telegram_delivery_budget_seconds: float
    remaining_budget_seconds_at_end: float | None
    summary_message: str

    def to_json_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write JSON atomically: temp file in same dir, fsync, os.replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent,
        prefix=".last_run_",
        suffix=".tmp",
        text=True,
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        with contextlib.suppress(OSError):
            tmp_path.unlink(missing_ok=True)
        raise
