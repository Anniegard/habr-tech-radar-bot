from __future__ import annotations

import logging
import sys

from habr_tech_radar.run_context import get_run_id

_CONFIGURED = False


class RunIdFilter(logging.Filter):
    """Injects run_id on every log record for root formatting."""

    def filter(self, record: logging.LogRecord) -> bool:
        rid = get_run_id()
        record.run_id = rid if rid is not None else "-"
        return True


def configure_logging(level: str) -> None:
    """Configure root logging once with a simple format (idempotent)."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    numeric = getattr(logging, level.upper(), logging.INFO)
    run_filter = RunIdFilter()
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s | %(levelname)s | %(name)s | run_id=%(run_id)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
        force=False,
    )
    for h in logging.root.handlers:
        h.addFilter(run_filter)
    _CONFIGURED = True
