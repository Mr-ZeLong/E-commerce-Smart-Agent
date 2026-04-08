"""v4.1: Add confidence audit and audit_level

Revision ID: v4_1_confidence
Revises: f84a99d62fad
Create Date: 2025-01-16

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = 'v4_1_confidence'
down_revision: Union[str, None] = 'f84a99d62fad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ========== 1. 添加 confidence_audits 表 ==========
    op.create_table(
        'confidence_audits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('thread_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('query', sa.Text(), nullable=False),
        sa.Column('confidence_score', sa.Float(), nullable=False),
        sa.Column('rag_score', sa.Float(), nullable=True),
        sa.Column('llm_score', sa.Float(), nullable=True),
        sa.Column('emotion_score', sa.Float(), nullable=True),
        sa.Column('signals_metadata', sa.JSON(), nullable=True),
        sa.Column('audit_level', sa.String(length=16), nullable=False),
        sa.Column('transfer_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(), nullable=True),
        sa.Column('reviewed_by', sa.Integer(), nullable=True),
        sa.Column('review_result', sa.String(length=16), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_confidence_audits_thread_id', 'confidence_audits', ['thread_id'])
    op.create_index('ix_confidence_audits_created_at', 'confidence_audits', ['created_at'])

    # ========== 2. 修改 audit_logs 表（添加 audit_level）==========
    op.add_column('audit_logs', sa.Column('audit_level', sa.String(length=16), nullable=True))

    # ========== 3. 数据迁移：设置默认 audit_level ==========
    op.execute("""
        UPDATE audit_logs
        SET audit_level = 'none'
        WHERE audit_level IS NULL
    """)


def downgrade() -> None:
    # ========== 1. 删除 confidence_audits 表 ==========
    op.drop_index('ix_confidence_audits_created_at', table_name='confidence_audits')
    op.drop_index('ix_confidence_audits_thread_id', table_name='confidence_audits')
    op.drop_table('confidence_audits')

    # ========== 2. 删除 audit_logs.audit_level ==========
    op.drop_column('audit_logs', 'audit_level')
