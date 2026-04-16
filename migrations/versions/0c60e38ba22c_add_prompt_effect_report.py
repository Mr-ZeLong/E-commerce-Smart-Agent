"""add_prompt_effect_report

Revision ID: 0c60e38ba22c
Revises: 46240a43ccc7
Create Date: 2026-04-16 23:52:30.639094

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision: str = "0c60e38ba22c"
down_revision: Union[str, None] = "46240a43ccc7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "prompt_effect_reports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("report_month", sqlmodel.sql.sqltypes.AutoString(length=7), nullable=False),
        sa.Column("agent_name", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("version_id", sa.Integer(), nullable=True),
        sa.Column("total_sessions", sa.Integer(), nullable=False),
        sa.Column("avg_confidence", sa.Float(), nullable=True),
        sa.Column("transfer_rate", sa.Float(), nullable=True),
        sa.Column("avg_latency_ms", sa.Float(), nullable=True),
        sa.Column("key_changes", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("recommendation", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["version_id"], ["agent_config_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("prompt_effect_reports")
