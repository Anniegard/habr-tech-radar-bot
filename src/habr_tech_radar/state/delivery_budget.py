from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DailyDeliveryBudget:
    """Track how many Telegram messages were sent today (UTC calendar day)."""

    path: Path

    def _today_utc(self) -> date:
        return datetime.now(UTC).date()

    def _load(self) -> tuple[date | None, int]:
        if not self.path.is_file():
            return None, 0
        try:
            raw = self.path.read_text(encoding="utf-8")
            data = json.loads(raw)
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as e:
            logger.warning(
                "delivery budget: could not read %s (%s), treating as empty",
                self.path,
                e,
            )
            return None, 0
        if not isinstance(data, dict):
            return None, 0
        day_raw = data.get("day_utc")
        count_raw = data.get("sent_today")
        if not isinstance(day_raw, str) or not isinstance(count_raw, int):
            return None, 0
        try:
            d = date.fromisoformat(day_raw)
        except ValueError:
            return None, 0
        return d, max(0, count_raw)

    def remaining_today(self, *, max_per_day: int) -> tuple[int, int]:
        """Return (remaining_budget, sent_today) for the current UTC day."""
        if max_per_day < 1:
            return 0, 0
        today = self._today_utc()
        day_stored, sent = self._load()
        if day_stored != today:
            return max_per_day, 0
        return max(0, max_per_day - sent), sent

    def record_sent(self, n: int) -> None:
        """Atomically add n to today's counter (UTC)."""
        if n <= 0:
            return
        today = self._today_utc()
        day_stored, sent = self._load()
        base = 0 if day_stored != today else sent
        new_count = base + n
        payload = {
            "day_utc": today.isoformat(),
            "sent_today": new_count,
            "updated_at_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(
            prefix=".delivery_budget_",
            suffix=".tmp",
            dir=self.path.parent,
        )
        tmp_path = Path(tmp_name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
                f.write("\n")
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self.path)
        except OSError:
            with contextlib.suppress(OSError):
                if tmp_path.exists():
                    tmp_path.unlink()
            raise
