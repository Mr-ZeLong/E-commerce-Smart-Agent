"""merge heads

Revision ID: 21ceb10df79d
Revises: drop_knowledge_chunks_table, e071d1fc293c
Create Date: 2026-04-09 19:26:57.329433

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = "21ceb10df79d"
down_revision: str | Sequence[str] | None = ("drop_knowledge_chunks_table", "e071d1fc293c")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
