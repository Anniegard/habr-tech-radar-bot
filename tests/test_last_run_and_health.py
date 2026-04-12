from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from habr_tech_radar.main import main
from habr_tech_radar.state.last_run import atomic_write_json


def test_atomic_write_json_creates_file(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "out.json"
    payload = {"a": 1, "b": "x"}
    atomic_write_json(target, payload)
    assert target.is_file()
    assert json.loads(target.read_text(encoding="utf-8")) == payload


def test_last_run_json_fields_after_demo_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    lr = tmp_path / "lr.json"
    monkeypatch.setenv("HTR_LAST_RUN_PATH", str(lr))
    code = main(["--demo"])
    assert code == 0
    data = json.loads(lr.read_text(encoding="utf-8"))
    for key in (
        "run_id",
        "started_at_utc",
        "finished_at_utc",
        "duration_seconds",
        "status",
        "exit_code",
        "fetched_count",
        "selected_count",
        "sent_count",
        "failed_count",
        "skipped_due_budget_count",
        "telegram_delivery_budget_seconds",
        "remaining_budget_seconds_at_end",
        "summary_message",
    ):
        assert key in data
    assert data["status"] == "success"
    assert data["exit_code"] == 0
    assert data["selected_count"] == 1


def test_health_summary_json_flag_implies_check(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    lr = tmp_path / "lr.json"
    finished = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    lr.write_text(
        json.dumps(
            {
                "run_id": "x",
                "started_at_utc": finished,
                "finished_at_utc": finished,
                "duration_seconds": 1.0,
                "status": "success",
                "exit_code": 0,
                "fetched_count": 1,
                "selected_count": 1,
                "sent_count": 1,
                "failed_count": 0,
                "skipped_due_budget_count": 0,
                "telegram_delivery_budget_seconds": 240.0,
                "remaining_budget_seconds_at_end": 200.0,
                "summary_message": "ok",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HTR_LAST_RUN_PATH", str(lr))
    monkeypatch.setenv("HTR_HEALTH_MAX_AGE_MINUTES", "99999")
    assert main(["--health-summary-json"]) == 0
    out = capsys.readouterr().out.strip()
    assert json.loads(out)["health_ok"] is True


def test_health_summary_ok_recent_success(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lr = tmp_path / "lr.json"
    finished = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    lr.write_text(
        json.dumps(
            {
                "run_id": "x",
                "started_at_utc": finished,
                "finished_at_utc": finished,
                "duration_seconds": 1.0,
                "status": "success",
                "exit_code": 0,
                "fetched_count": 1,
                "selected_count": 1,
                "sent_count": 1,
                "failed_count": 0,
                "skipped_due_budget_count": 0,
                "telegram_delivery_budget_seconds": 240.0,
                "remaining_budget_seconds_at_end": 200.0,
                "summary_message": "ok",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HTR_LAST_RUN_PATH", str(lr))
    monkeypatch.setenv("HTR_HEALTH_MAX_AGE_MINUTES", "99999")
    assert main(["--health-summary"]) == 0


def test_health_summary_fails_on_missing_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HTR_LAST_RUN_PATH", str(tmp_path / "nope.json"))
    assert main(["--health-summary"]) == 1


def test_health_summary_fails_when_stale(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lr = tmp_path / "lr.json"
    old = (datetime.now(UTC) - timedelta(hours=10)).strftime("%Y-%m-%dT%H:%M:%SZ")
    lr.write_text(
        json.dumps(
            {
                "run_id": "x",
                "started_at_utc": old,
                "finished_at_utc": old,
                "duration_seconds": 1.0,
                "status": "success",
                "exit_code": 0,
                "fetched_count": 0,
                "selected_count": 0,
                "sent_count": 0,
                "failed_count": 0,
                "skipped_due_budget_count": 0,
                "telegram_delivery_budget_seconds": 240.0,
                "remaining_budget_seconds_at_end": None,
                "summary_message": "x",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HTR_LAST_RUN_PATH", str(lr))
    monkeypatch.setenv("HTR_HEALTH_MAX_AGE_MINUTES", "60")
    assert main(["--health-summary"]) == 1


def test_health_summary_fails_when_not_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lr = tmp_path / "lr.json"
    finished = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    lr.write_text(
        json.dumps(
            {
                "run_id": "x",
                "started_at_utc": finished,
                "finished_at_utc": finished,
                "duration_seconds": 1.0,
                "status": "partial",
                "exit_code": 1,
                "fetched_count": 1,
                "selected_count": 1,
                "sent_count": 0,
                "failed_count": 0,
                "skipped_due_budget_count": 1,
                "telegram_delivery_budget_seconds": 240.0,
                "remaining_budget_seconds_at_end": 0.0,
                "summary_message": "x",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("HTR_LAST_RUN_PATH", str(lr))
    monkeypatch.setenv("HTR_HEALTH_MAX_AGE_MINUTES", "99999")
    assert main(["--health-summary"]) == 1


def test_run_start_log_contains_run_id(
    caplog: pytest.LogCaptureFixture,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    caplog.set_level("INFO")
    main(["--demo"])
    joined = " ".join(rec.message for rec in caplog.records)
    assert "run start run_id=" in joined

