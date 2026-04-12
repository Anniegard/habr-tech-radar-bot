from __future__ import annotations

import logging
import sys

_CONFIGURED = False


def configure_logging(level: str) -> None:
    """Configure root logging once with a simple format (idempotent)."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    numeric = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        level=numeric,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stderr,
        force=False,
    )
    _CONFIGURED = True
