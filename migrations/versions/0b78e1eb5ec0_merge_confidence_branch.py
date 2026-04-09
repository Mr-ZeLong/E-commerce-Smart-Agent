"""merge confidence branch

Revision ID: 0b78e1eb5ec0
Revises: 6ee40b0ef47f, v4_2_confidence_trigger
Create Date: 2026-04-08 14:33:07.042083

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = '0b78e1eb5ec0'
down_revision: Union[str, Sequence[str], None] = ('6ee40b0ef47f', 'v4_2_confidence_trigger')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
