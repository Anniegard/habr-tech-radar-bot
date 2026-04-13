from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from habr_tech_radar.state.delivery_budget import DailyDeliveryBudget


def test_daily_budget_resets_on_new_utc_day(tmp_path: Path) -> None:
    p = tmp_path / "b.json"
    b = DailyDeliveryBudget(p)

    # Simulate "yesterday" in file
    yesterday = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    p.write_text(
        json.dumps({"day_utc": yesterday, "sent_today": 100}),
        encoding="utf-8",
    )
    rem, sent = b.remaining_today(max_per_day=25)
    assert sent == 0
    assert rem == 25


def test_record_sent_updates_file(tmp_path: Path) -> None:
    p = tmp_path / "b.json"
    b = DailyDeliveryBudget(p)
    b.record_sent(2)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["sent_today"] == 2
    assert data["day_utc"] == datetime.now(UTC).date().isoformat()
