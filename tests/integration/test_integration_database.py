import os
from datetime import date
from pathlib import Path

from sqlalchemy import create_engine, text

from services.ingestion.db.repository import TelemetryRepository
from services.ingestion.sources.grid_india_psp import parse_grid_india_psp_csv

FIXTURE_PATH = Path("tests/fixtures/grid_india/psp_2026-08-19_15min.csv")


def test_psp_fixture_is_inserted_into_database() -> None:
    database_url = os.environ["DATABASE_URL"]

    csv_text = FIXTURE_PATH.read_text(encoding="utf-8")

    telemetry = parse_grid_india_psp_csv(
        csv_text,
        report_date=date(2026, 8, 19),
    )

    repository = TelemetryRepository(database_url)

    try:
        for record in telemetry:
            repository.insert(record)
    finally:
        repository.close()

    engine = create_engine(database_url)

    try:
        with engine.connect() as connection:
            count = connection.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM telemetry
                    WHERE source = 'grid_india_nldc_psp'
                      AND entity = 'all_india'
                    """
                )
            ).scalar_one()

        assert count > 0

    finally:
        engine.dispose()
