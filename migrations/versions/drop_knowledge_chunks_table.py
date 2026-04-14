"""drop knowledge_chunks table

Revision ID: drop_knowledge_chunks_table
Revises: v4_2_confidence_trigger
Create Date: 2026-04-09
"""

from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "drop_knowledge_chunks_table"
down_revision: Union[str, None] = "v4_2_confidence_trigger"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
