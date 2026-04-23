"""add_experiment_metrics_table

Revision ID: f8a2b3c4d5e6
Revises: 053eaa2f0a66
Create Date: 2026-04-23 17:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f8a2b3c4d5e6"
down_revision: str | None = "a5d7c3dd7bd7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Create experiment_metrics table
    op.create_table(
        "experiment_metrics",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("variant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("needs_human_transfer", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["experiment_variants.id"],
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_experiment_metrics_variant_id"),
        "experiment_metrics",
        ["variant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_experiment_metrics_user_id"),
        "experiment_metrics",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_experiment_metrics_user_id"), table_name="experiment_metrics")
    op.drop_index(op.f("ix_experiment_metrics_variant_id"), table_name="experiment_metrics")
    op.drop_table("experiment_metrics")
