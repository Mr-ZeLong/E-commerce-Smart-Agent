"""add_agent_config_audit_log

Revision ID: 5cc243312e9f
Revises: 1bdaad9153a3
Create Date: 2026-04-12 13:00:30.109723

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision: str = "5cc243312e9f"
down_revision: Union[str, None] = "1bdaad9153a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agent_config_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("agent_name", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("changed_by", sa.Integer(), nullable=False),
        sa.Column("field_name", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("old_value", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("new_value", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_agent_config_audit_logs_agent_name"),
        "agent_config_audit_logs",
        ["agent_name"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_agent_config_audit_logs_agent_name"), table_name="agent_config_audit_logs"
    )
    op.drop_table("agent_config_audit_logs")
