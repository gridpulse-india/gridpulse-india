import argparse
import logging
from datetime import date
from pathlib import Path

from services.ingestion.logging_config import (
    configure_json_logging,
)
from services.ingestion.poller import Poller
from services.ingestion.sources.grid_india_psp import (
    SOURCE_NAME,
    parse_grid_india_psp_csv,
)

DEFAULT_FIXTURE_PATH = Path("tests/fixtures/grid_india/psp_2026-08-19_15min.csv")

DEFAULT_REPORT_DATE = date(
    2026,
    8,
    19,
)


def poll_fixture(
    *,
    fixture_path: Path,
    report_date: date,
):
    raw_csv = fixture_path.read_text(encoding="utf-8")

    return parse_grid_india_psp_csv(
        raw_csv,
        report_date=report_date,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the GridPulse ingestion poller.")

    parser.add_argument(
        "--interval-seconds",
        type=float,
        default=60.0,
    )

    parser.add_argument(
        "--duration-seconds",
        type=float,
        default=None,
    )

    parser.add_argument(
        "--max-runs",
        type=int,
        default=None,
    )

    parser.add_argument(
        "--fixture-path",
        type=Path,
        default=DEFAULT_FIXTURE_PATH,
    )

    parser.add_argument(
        "--report-date",
        type=date.fromisoformat,
        default=DEFAULT_REPORT_DATE,
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    configure_json_logging()

    logger = logging.getLogger("gridpulse.ingestion.runner")

    poller = Poller(
        source=SOURCE_NAME,
        interval_seconds=args.interval_seconds,
        poll_fn=lambda: poll_fixture(
            fixture_path=args.fixture_path,
            report_date=args.report_date,
        ),
    )

    try:
        poller.run(
            duration_seconds=args.duration_seconds,
            max_runs=args.max_runs,
        )
    except KeyboardInterrupt:
        logger.info(
            "poller_interrupted",
            extra={
                "source": SOURCE_NAME,
            },
        )


if __name__ == "__main__":
    main()
