"""add agent_config previous_system_prompt

Revision ID: 1bdaad9153a3
Revises: 648e66f44116
Create Date: 2026-04-12 12:09:05.531131

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision: str = "1bdaad9153a3"
down_revision: Union[str, None] = "648e66f44116"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("agent_configs")]
    if "previous_system_prompt" not in columns:
        op.add_column(
            "agent_configs",
            sa.Column("previous_system_prompt", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("agent_configs")]
    if "previous_system_prompt" in columns:
        op.drop_column("agent_configs", "previous_system_prompt")
