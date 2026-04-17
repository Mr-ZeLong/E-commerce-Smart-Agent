"""add memory_context_config to experiment_variants

Revision ID: bcacde2204d2
Revises: 0c60e38ba22c
Create Date: 2026-04-17 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "bcacde2204d2"
down_revision: str | None = "0c60e38ba22c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "experiment_variants",
        sa.Column("memory_context_config", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("experiment_variants", "memory_context_config")
