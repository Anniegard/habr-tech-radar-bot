from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DeliveryStats:
    """Result of TelegramDelivery.send (live, dry_run, or log-only)."""

    sent: int
    failed: int
    skipped_due_budget: int
    remaining_budget_seconds_at_end: float | None = None
