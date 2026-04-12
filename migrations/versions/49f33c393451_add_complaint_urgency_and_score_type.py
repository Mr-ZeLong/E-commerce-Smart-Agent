"""add_complaint_urgency_and_score_type

Revision ID: 49f33c393451
Revises: 053eaa2f0a66
Create Date: 2026-04-12 19:44:55.166178

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision: str = "49f33c393451"
down_revision: Union[str, None] = "053eaa2f0a66"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "complaint_tickets",
        sa.Column("urgency", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
    )
    op.execute("UPDATE complaint_tickets SET urgency = 'medium' WHERE urgency IS NULL")
    op.alter_column("complaint_tickets", "urgency", nullable=False)
    op.add_column(
        "quality_scores",
        sa.Column("score_type", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
    )
    op.execute("UPDATE quality_scores SET score_type = 'overall' WHERE score_type IS NULL")
    op.alter_column("quality_scores", "score_type", nullable=False)


def downgrade() -> None:
    op.drop_column("quality_scores", "score_type")
    op.drop_column("complaint_tickets", "urgency")
