"""add_context_utilization_to_graph_execution_log

Revision ID: a5d7c3dd7bd7
Revises: bcacde2204d2
Create Date: 2026-04-17 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a5d7c3dd7bd7"
down_revision: str | None = "bcacde2204d2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "graph_execution_logs",
        sa.Column("context_tokens", sa.Integer(), nullable=True),
    )
    op.add_column(
        "graph_execution_logs",
        sa.Column("context_utilization", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("graph_execution_logs", "context_utilization")
    op.drop_column("graph_execution_logs", "context_tokens")
