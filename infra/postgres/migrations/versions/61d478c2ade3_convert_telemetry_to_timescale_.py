"""convert telemetry to timescale hypertable

Revision ID: 61d478c2ade3
Revises: b9e063fb4e7a
"""

from collections.abc import Sequence

from alembic import op

revision: str = "61d478c2ade3"
down_revision: str | None = "b9e063fb4e7a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Convert telemetry into a TimescaleDB hypertable."""

    op.drop_constraint(
        "uq_telemetry_event_id",
        "telemetry",
        type_="unique",
    )

    op.create_unique_constraint(
        "uq_telemetry_event_id_observed_at",
        "telemetry",
        ["event_id", "observed_at"],
    )

    op.execute(
        """
        SELECT create_hypertable(
            'telemetry',
            'observed_at',
            if_not_exists => TRUE,
            migrate_data => TRUE
        );
        """
    )


def downgrade() -> None:
    """Hypertable conversion is intentionally not automatically reversed."""

    raise RuntimeError(
        "Downgrading a TimescaleDB hypertable to a regular PostgreSQL "
        "table requires an explicit data migration."
    )
