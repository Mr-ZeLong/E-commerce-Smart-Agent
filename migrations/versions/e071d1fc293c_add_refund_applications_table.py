"""add refund_applications table

Revision ID: e071d1fc293c
Revises: 0b78e1eb5ec0
Create Date: 2026-04-09 13:26:19.647025

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e071d1fc293c'
down_revision: str | None = '0b78e1eb5ec0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table('refund_applications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('reason_category', sa.String(), nullable=True),
        sa.Column('reason_detail', sa.Text(), nullable=False),
        sa.Column('refund_amount', sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column('admin_note', sa.Text(), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), onupdate=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.ForeignKeyConstraint(['order_id'], ['orders.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_refund_applications_order_id'), 'refund_applications', ['order_id'], unique=False)
    op.create_index(op.f('ix_refund_applications_status'), 'refund_applications', ['status'], unique=False)
    op.create_index(op.f('ix_refund_applications_user_id'), 'refund_applications', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_refund_applications_user_id'), table_name='refund_applications')
    op.drop_index(op.f('ix_refund_applications_status'), table_name='refund_applications')
    op.drop_index(op.f('ix_refund_applications_order_id'), table_name='refund_applications')
    op.drop_table('refund_applications')
