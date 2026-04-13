from __future__ import annotations

import argparse
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from habr_tech_radar.config.preset import apply_preset_env_overlay
from habr_tech_radar.delivery.http_telegram import (
    TelegramConfigurationError,
    TelegramDeliveryError,
)
from habr_tech_radar.health_summary import run_health_summary
from habr_tech_radar.logging_config import configure_logging
from habr_tech_radar.pipeline import PipelineResult, default_components, run_pipeline
from habr_tech_radar.run_context import generate_run_id, set_run_id
from habr_tech_radar.settings import (
    Settings,
    effective_last_run_path,
    effective_last_run_path_from_env,
)
from habr_tech_radar.state.last_run import LastRunRecord, LastRunStatus, atomic_write_json

logger = logging.getLogger(__name__)


def _delivery_status_from_stats(stats: object | None) -> LastRunStatus:
    """Map TelegramDeliveryError stats to partial vs failed."""
    if stats is None:
        return "failed"
    sent = int(getattr(stats, "sent", 0))
    skipped = int(getattr(stats, "skipped_due_budget", 0))
    skipped_daily = int(getattr(stats, "skipped_due_daily_cap", 0))
    if sent > 0 or skipped > 0 or skipped_daily > 0:
        return "partial"
    return "failed"


def _persist_last_run_best_effort(record: LastRunRecord, *, path: Path) -> None:
    atomic_write_json(path, record.to_json_dict())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Habr Tech Radar (MVP scaffold)")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Ingest one synthetic article and run the full pipeline (no network)",
    )
    parser.add_argument(
        "--health-summary",
        action="store_true",
        help="Print last run health from HTR_LAST_RUN_PATH and exit (0 = healthy)",
    )
    parser.add_argument(
        "--health-summary-json",
        action="store_true",
        help="Health check: print JSON (implies --health-summary; includes health_ok)",
    )
    args = parser.parse_args(argv)

    if args.health_summary or args.health_summary_json:
        try:
            settings = apply_preset_env_overlay(Settings())
        except ValidationError as e:
            print(f"health: invalid settings: {e}", file=sys.stderr)
            return 2
        configure_logging(settings.log_level)
        return run_health_summary(
            settings,
            json_output=args.health_summary_json,
        )

    run_id = generate_run_id()
    set_run_id(run_id)
    started_at = datetime.now(UTC)

    try:
        settings = Settings()
    except ValidationError as e:
        configure_logging("INFO")
        logging.getLogger(__name__).error("fatal: invalid configuration: %s", e)
        _try_write_failed_config(run_id, started_at, str(e))
        return 2

    if args.demo:
        settings = settings.model_copy(update={"demo_mode": True})
    elif not settings.demo_mode:
        settings = apply_preset_env_overlay(settings)
    configure_logging(settings.log_level)

    logger.info(
        "run start run_id=%s dry_run=%s demo=%s",
        run_id,
        settings.dry_run,
        settings.demo_mode,
    )

    last_path = effective_last_run_path(settings)
    budget_s = float(settings.telegram_max_delivery_seconds)

    fetched_count = 0
    selected_count = 0
    filtered_passed = 0
    filtered_rejected = 0
    ranked_count = 0
    rss_feeds_configured: int | None = None
    rss_feeds_fetched_ok: int | None = None
    rss_items_parsed: int | None = None
    rss_unique_items: int | None = None
    rss_new_items: int | None = None
    rss_skipped_seen: int | None = None
    sent_count = 0
    failed_count = 0
    skipped_due_budget_count = 0
    skipped_due_daily_cap_count = 0
    remaining_budget: float | None = None
    exit_code = 1
    status: LastRunStatus = "failed"

    try:
        components = default_components(settings)
        result: PipelineResult = run_pipeline(components)
        fetched_count = result.fetched_count
        selected_count = result.selected_count
        filtered_passed = result.filtered_passed
        filtered_rejected = result.filtered_rejected
        ranked_count = result.ranked_count
        if result.ingestion_metrics is not None:
            m = result.ingestion_metrics
            rss_feeds_configured = m.feeds_configured
            rss_feeds_fetched_ok = m.feeds_fetched_ok
            rss_items_parsed = m.items_parsed_total
            rss_unique_items = m.items_after_cross_feed_dedup
            rss_new_items = m.items_new
            rss_skipped_seen = m.items_skipped_seen
        sent_count = result.delivery_stats.sent
        failed_count = result.delivery_stats.failed
        skipped_due_budget_count = result.delivery_stats.skipped_due_budget
        skipped_due_daily_cap_count = result.delivery_stats.skipped_due_daily_cap
        remaining_budget = result.delivery_stats.remaining_budget_seconds_at_end
        exit_code = 0
        status = "success"
        logger.info(
            "run finished run_id=%s status=success fetched=%d selected=%d sent=%d "
            "failed=%d skipped_due_budget=%d skipped_due_daily_cap=%d",
            run_id,
            fetched_count,
            selected_count,
            sent_count,
            failed_count,
            skipped_due_budget_count,
            skipped_due_daily_cap_count,
        )
    except TelegramConfigurationError as e:
        logger.error("%s", e)
        exit_code = 2
        status = "config_error"
        logger.info("run finished run_id=%s status=config_error", run_id)
    except TelegramDeliveryError as e:
        logger.error("%s", e)
        exit_code = 1
        stats = e.stats
        status = _delivery_status_from_stats(stats)
        fetched_count = int(e.fetched_count or 0)
        selected_count = int(e.selected_count or 0)
        if stats is not None:
            sent_count = stats.sent
            failed_count = stats.failed
            skipped_due_budget_count = stats.skipped_due_budget
            skipped_due_daily_cap_count = getattr(stats, "skipped_due_daily_cap", 0)
            remaining_budget = stats.remaining_budget_seconds_at_end
        logger.info(
            "run finished run_id=%s status=%s fetched=%d selected=%d sent=%d "
            "failed=%d skipped_due_budget=%d skipped_due_daily_cap=%d",
            run_id,
            status,
            fetched_count,
            selected_count,
            sent_count,
            failed_count,
            skipped_due_budget_count,
            skipped_due_daily_cap_count,
        )
    except BaseException as e:
        logger.exception("fatal: %s", e)
        exit_code = 1
        status = "failed"
        logger.info("run finished run_id=%s status=failed", run_id)
    finally:
        finished_at = datetime.now(UTC)
        duration = (finished_at - started_at).total_seconds()
        summary_message = (
            f"fetched={fetched_count} filter_pass={filtered_passed} "
            f"filter_reject={filtered_rejected} ranked={ranked_count} "
            f"selected={selected_count} sent={sent_count} "
            f"failed={failed_count} skipped_due_budget={skipped_due_budget_count} "
            f"skipped_due_daily_cap={skipped_due_daily_cap_count} status={status}"
        )
        record = LastRunRecord(
            run_id=run_id,
            started_at_utc=started_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            finished_at_utc=finished_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            duration_seconds=round(duration, 3),
            status=status,
            exit_code=exit_code,
            fetched_count=fetched_count,
            selected_count=selected_count,
            filtered_passed=filtered_passed,
            filtered_rejected=filtered_rejected,
            ranked_count=ranked_count,
            rss_feeds_configured=rss_feeds_configured,
            rss_feeds_fetched_ok=rss_feeds_fetched_ok,
            rss_items_parsed=rss_items_parsed,
            rss_unique_items=rss_unique_items,
            rss_new_items=rss_new_items,
            rss_skipped_seen=rss_skipped_seen,
            sent_count=sent_count,
            failed_count=failed_count,
            skipped_due_budget_count=skipped_due_budget_count,
            skipped_due_daily_cap_count=skipped_due_daily_cap_count,
            telegram_delivery_budget_seconds=budget_s,
            remaining_budget_seconds_at_end=remaining_budget,
            summary_message=summary_message,
        )
        try:
            _persist_last_run_best_effort(record, path=last_path)
        except OSError as e:
            logger.warning("last_run: could not write %s: %s", last_path, e)
        logger.info(
            "run summary: %s",
            summary_message,
        )

    return exit_code


def _try_write_failed_config(run_id: str, started_at: datetime, err: str) -> None:
    """Best-effort last_run when Settings() does not parse."""
    try:
        path = effective_last_run_path_from_env()
        finished_at = datetime.now(UTC)
        summary_message = f"status=config_error error={err[:200]}"
        record = LastRunRecord(
            run_id=run_id,
            started_at_utc=started_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            finished_at_utc=finished_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            duration_seconds=round((finished_at - started_at).total_seconds(), 3),
            status="config_error",
            exit_code=2,
            fetched_count=0,
            selected_count=0,
            filtered_passed=0,
            filtered_rejected=0,
            ranked_count=0,
            rss_feeds_configured=None,
            rss_feeds_fetched_ok=None,
            rss_items_parsed=None,
            rss_unique_items=None,
            rss_new_items=None,
            rss_skipped_seen=None,
            sent_count=0,
            failed_count=0,
            skipped_due_budget_count=0,
            skipped_due_daily_cap_count=0,
            telegram_delivery_budget_seconds=0.0,
            remaining_budget_seconds_at_end=None,
            summary_message=summary_message,
        )
        atomic_write_json(path, record.to_json_dict())
    except OSError:
        pass


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
