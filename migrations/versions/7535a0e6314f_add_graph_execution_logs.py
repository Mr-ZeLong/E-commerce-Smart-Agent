"""add graph execution logs

Revision ID: 7535a0e6314f
Revises: 11c9030366ba
Create Date: 2026-04-12 00:55:02.082688

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "7535a0e6314f"
down_revision: Union[str, None] = "11c9030366ba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "graph_execution_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("intent_category", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
        sa.Column("final_agent", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("needs_human_transfer", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("total_latency_ms", sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_graph_execution_logs_intent_category"),
        "graph_execution_logs",
        ["intent_category"],
        unique=False,
    )
    op.create_index(
        op.f("ix_graph_execution_logs_thread_id"),
        "graph_execution_logs",
        ["thread_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_graph_execution_logs_user_id"), "graph_execution_logs", ["user_id"], unique=False
    )
    op.create_table(
        "graph_node_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("execution_id", sa.Integer(), nullable=False),
        sa.Column("node_name", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["execution_id"], ["graph_execution_logs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_graph_node_logs_execution_id"), "graph_node_logs", ["execution_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_graph_node_logs_execution_id"), table_name="graph_node_logs")
    op.drop_table("graph_node_logs")
    op.drop_index(op.f("ix_graph_execution_logs_user_id"), table_name="graph_execution_logs")
    op.drop_index(op.f("ix_graph_execution_logs_thread_id"), table_name="graph_execution_logs")
    op.drop_index(
        op.f("ix_graph_execution_logs_intent_category"), table_name="graph_execution_logs"
    )
    op.drop_table("graph_execution_logs")
