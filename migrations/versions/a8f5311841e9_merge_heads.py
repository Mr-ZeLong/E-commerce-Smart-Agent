"""merge heads

Revision ID: a8f5311841e9
Revises: f8a2b3c4d5e6, 3a9f8e7b2c1d
Create Date: 2026-04-24 00:20:21.232797

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = 'a8f5311841e9'
down_revision: Union[str, None] = ('f8a2b3c4d5e6', '3a9f8e7b2c1d')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
