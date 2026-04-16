"""add_agent_config_versions

Revision ID: ad240cc404ba
Revises: add_order_delivered_at_fk
Create Date: 2026-04-16 23:19:20.573510

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision: str = "ad240cc404ba"
down_revision: Union[str, None] = "add_order_delivered_at_fk"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_config_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_name", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("changed_by", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("confidence_threshold", sa.Float(), nullable=False),
        sa.Column("max_retries", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["changed_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_config_versions_agent_name"),
        "agent_config_versions",
        ["agent_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_agent_config_versions_agent_name"),
        table_name="agent_config_versions",
    )
    op.drop_table("agent_config_versions")
