from datetime import datetime

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from services.ingestion.models import CanonicalTelemetry


class TelemetryRepository:
    """Persistence operations for canonical telemetry."""

    def __init__(self, database_url: str) -> None:
        self._engine: Engine = create_engine(database_url)

    def insert(self, telemetry: CanonicalTelemetry) -> bool:
        """Insert telemetry if its event_id does not already exist.

        Returns True when a new row is inserted and False when the
        event_id was already present.
        """

        query = text(
            """
            INSERT INTO telemetry (
                event_id,
                source,
                entity,
                metric,
                value,
                unit,
                observed_at,
                ingested_at,
                quality,
                schema_version
            )
            VALUES (
                :event_id,
                :source,
                :entity,
                :metric,
                :value,
                :unit,
                :observed_at,
                :ingested_at,
                :quality,
                :schema_version
            )
            ON CONFLICT (event_id, observed_at) DO NOTHING
            """
        )

        values = {
            "event_id": telemetry.event_id,
            "source": telemetry.source,
            "entity": telemetry.entity,
            "metric": telemetry.metric,
            "value": telemetry.value,
            "unit": telemetry.unit,
            "observed_at": telemetry.observed_at,
            "ingested_at": telemetry.ingested_at or datetime.now(telemetry.observed_at.tzinfo),
            "quality": telemetry.quality,
            "schema_version": telemetry.schema_version,
        }

        with self._engine.begin() as connection:
            result = connection.execute(query, values)

        return result.rowcount == 1

    def close(self) -> None:
        """Dispose of the database connection pool."""

        self._engine.dispose()
