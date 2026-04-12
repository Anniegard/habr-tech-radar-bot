from __future__ import annotations

import secrets
from contextvars import ContextVar
from datetime import UTC, datetime

_run_id_var: ContextVar[str | None] = ContextVar("run_id", default=None)


def generate_run_id(now: datetime | None = None) -> str:
    """Readable unique id: YYYYMMDDTHHMMSSZ + '-' + 8 hex chars (UTC)."""
    dt = (now or datetime.now(UTC)).astimezone(UTC)
    stamp = dt.strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{secrets.token_hex(4)}"


def set_run_id(run_id: str) -> None:
    _run_id_var.set(run_id)


def get_run_id() -> str | None:
    return _run_id_var.get()
