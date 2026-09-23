"""Persist forecast coordinates for map points.

Revision ID: 5f0e7c29b4a1
Revises: 4a8c1e7d2b90
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "5f0e7c29b4a1"
down_revision: str | None = "4a8c1e7d2b90"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Existing demonstration and cached forecasts have no trustworthy coordinates.
    # Leave them null; the next successful geocoded sync populates real coordinates.
    with op.batch_alter_table("forecasts") as batch:
        batch.add_column(sa.Column("latitude", sa.Numeric(9, 6), nullable=True))
        batch.add_column(sa.Column("longitude", sa.Numeric(9, 6), nullable=True))
        batch.create_check_constraint(
            "ck_forecast_lat", "latitude IS NULL OR latitude BETWEEN -90 AND 90"
        )
        batch.create_check_constraint(
            "ck_forecast_lon", "longitude IS NULL OR longitude BETWEEN -180 AND 180"
        )
        batch.create_check_constraint(
            "ck_forecast_coordinates_pair",
            "(latitude IS NULL AND longitude IS NULL) OR "
            "(latitude IS NOT NULL AND longitude IS NOT NULL)",
        )
        batch.create_index("ix_forecasts_coords_valid", ["latitude", "longitude", "valid_until"])

    # Official INMET notices can describe an area in text without a CAP polygon.
    # Manual and demonstration alerts still require a mapped area.
    with op.batch_alter_table("weather_alerts") as batch:
        batch.drop_constraint("ck_alert_has_area", type_="check")
        batch.create_check_constraint(
            "ck_alert_has_area",
            "origin = 'INMET' OR polygon IS NOT NULL OR "
            "(latitude IS NOT NULL AND longitude IS NOT NULL AND radius_km IS NOT NULL)",
        )


def downgrade() -> None:
    # Do not silently remove official notices or make the database invalid.
    # Reverting this schema requires assigning a real area to every such notice.
    connection = op.get_bind()
    no_area_count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM weather_alerts "
            "WHERE polygon IS NULL AND NOT "
            "(latitude IS NOT NULL AND longitude IS NOT NULL AND radius_km IS NOT NULL)"
        )
    ).scalar_one()
    if no_area_count:
        raise RuntimeError(
            "Não é possível reverter: existem avisos do INMET sem geometria. "
            "Defina uma área real para cada aviso antes de reverter."
        )

    with op.batch_alter_table("weather_alerts") as batch:
        batch.drop_constraint("ck_alert_has_area", type_="check")
        batch.create_check_constraint(
            "ck_alert_has_area",
            "polygon IS NOT NULL OR "
            "(latitude IS NOT NULL AND longitude IS NOT NULL AND radius_km IS NOT NULL)",
        )

    with op.batch_alter_table("forecasts") as batch:
        batch.drop_index("ix_forecasts_coords_valid")
        batch.drop_constraint("ck_forecast_coordinates_pair", type_="check")
        batch.drop_constraint("ck_forecast_lon", type_="check")
        batch.drop_constraint("ck_forecast_lat", type_="check")
        batch.drop_column("longitude")
        batch.drop_column("latitude")
