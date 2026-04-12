from __future__ import annotations

import argparse
import logging
import sys

from habr_tech_radar.logging_config import configure_logging
from habr_tech_radar.pipeline import default_components, run_pipeline
from habr_tech_radar.settings import Settings

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Habr Tech Radar (MVP scaffold)")
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Ingest one synthetic article and run the full pipeline (no network)",
    )
    args = parser.parse_args(argv)

    settings = Settings()
    if args.demo:
        settings = settings.model_copy(update={"demo_mode": True})
    configure_logging(settings.log_level)

    logger.info(
        "starting habr-tech-radar dry_run=%s demo=%s",
        settings.dry_run,
        settings.demo_mode,
    )
    components = default_components(settings)
    run_pipeline(components)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
