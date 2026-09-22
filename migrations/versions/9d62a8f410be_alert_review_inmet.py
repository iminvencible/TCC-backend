"""alert review, provenance, audit and admin role

Revision ID: 9d62a8f410be
Revises: b6f535f44c51
Create Date: 2026-09-21 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "9d62a8f410be"
down_revision: str | None = "b6f535f44c51"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "UPDATE roles SET code = 'ADMIN', display_name = 'Administrador' WHERE code = 'OWNER'"
    )
    op.execute("UPDATE roles SET display_name = 'Usuário' WHERE code = 'USER'")
    with op.batch_alter_table("weather_alerts") as batch:
        batch.add_column(
            sa.Column("origin", sa.String(length=16), server_default="MANUAL", nullable=False)
        )
        batch.add_column(
            sa.Column(
                "source_name", sa.String(length=120), server_default="PrevClima", nullable=False
            )
        )
        batch.add_column(sa.Column("source_url", sa.String(length=500), nullable=True))
        batch.add_column(
            sa.Column(
                "validation_status",
                sa.String(length=24),
                server_default="ACTIVE",
                nullable=False,
            )
        )
        batch.add_column(sa.Column("status_reason", sa.Text(), nullable=True))
        batch.add_column(sa.Column("status_changed_by", sa.Integer(), nullable=True))
        batch.add_column(sa.Column("status_changed_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_check_constraint("ck_alert_origin", "origin IN ('DEMO', 'MANUAL', 'INMET')")
        batch.create_check_constraint(
            "ck_alert_validation_status",
            "validation_status IN ('ACTIVE', 'FALSE_ALARM', 'NEEDS_CORRECTION')",
        )
        batch.create_foreign_key(
            "fk_weather_alerts_status_changed_by_users",
            "users",
            ["status_changed_by"],
            ["id"],
            ondelete="SET NULL",
        )
        batch.create_index(
            "ix_alerts_validation", ["validation_status", "valid_until"], unique=False
        )
    op.execute(
        "UPDATE weather_alerts SET origin = 'DEMO', "
        "source_name = 'PrevClima - demonstracao' WHERE is_demo = TRUE"
    )
    op.create_table(
        "alert_reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("alert_id", sa.Integer(), nullable=False),
        sa.Column("reviewer_id", sa.Integer(), nullable=False),
        sa.Column("previous_status", sa.String(length=24), nullable=False),
        sa.Column("new_status", sa.String(length=24), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "previous_status IN ('ACTIVE', 'FALSE_ALARM', 'NEEDS_CORRECTION')",
            name="ck_alert_review_previous_status",
        ),
        sa.CheckConstraint(
            "new_status IN ('ACTIVE', 'FALSE_ALARM', 'NEEDS_CORRECTION')",
            name="ck_alert_review_new_status",
        ),
        sa.ForeignKeyConstraint(["alert_id"], ["weather_alerts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_alert_reviews_alert_created",
        "alert_reviews",
        ["alert_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("target_type", sa.String(length=50), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_target_created",
        "audit_events",
        ["target_type", "target_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_audit_target_created", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_alert_reviews_alert_created", table_name="alert_reviews")
    op.drop_table("alert_reviews")
    with op.batch_alter_table("weather_alerts") as batch:
        batch.drop_index("ix_alerts_validation")
        batch.drop_constraint("fk_weather_alerts_status_changed_by_users", type_="foreignkey")
        batch.drop_constraint("ck_alert_validation_status", type_="check")
        batch.drop_constraint("ck_alert_origin", type_="check")
        batch.drop_column("status_changed_at")
        batch.drop_column("status_changed_by")
        batch.drop_column("status_reason")
        batch.drop_column("validation_status")
        batch.drop_column("source_url")
        batch.drop_column("source_name")
        batch.drop_column("origin")
    op.execute(
        "UPDATE roles SET code = 'OWNER', display_name = 'Administrador' WHERE code = 'ADMIN'"
    )
    op.execute("UPDATE roles SET display_name = 'Usuario' WHERE code = 'USER'")
