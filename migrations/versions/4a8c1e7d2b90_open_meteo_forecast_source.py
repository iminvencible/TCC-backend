"""open meteo forecast source

Revision ID: 4a8c1e7d2b90
Revises: 9d62a8f410be
Create Date: 2026-09-22 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "4a8c1e7d2b90"
down_revision: str | None = "9d62a8f410be"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("forecasts") as batch:
        batch.add_column(sa.Column("source_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("forecasts") as batch:
        batch.drop_column("source_url")
