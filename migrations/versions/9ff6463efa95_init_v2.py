"""init_v2

Revision ID: 9ff6463efa95
Revises:
Create Date: 2026-01-11 20:42:05.402410

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = "9ff6463efa95"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
