"""v4.2: Add confidence audit trigger type

Revision ID: v4_2_confidence_trigger
Revises: v4_1_confidence
Create Date: 2025-01-17

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = 'v4_2_confidence_trigger'
down_revision: Union[str, None] = 'v4_1_confidence'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 创建枚举类型（如果不存在）
    op.execute("CREATE TYPE audittriggertype AS ENUM ('RISK', 'CONFIDENCE', 'MANUAL')")

    # 添加 trigger_type 列
    op.add_column(
        'audit_logs',
        sa.Column(
            'trigger_type',
            sa.Enum('RISK', 'CONFIDENCE', 'MANUAL', name='audittriggertype'),
            nullable=False,
            server_default='RISK'
        )
    )

    # 添加 confidence_metadata 列
    op.add_column(
        'audit_logs',
        sa.Column('confidence_metadata', sa.JSON(), nullable=True)
    )

    # 创建索引
    op.create_index('ix_audit_logs_trigger_type', 'audit_logs', ['trigger_type'])


def downgrade() -> None:
    op.drop_index('ix_audit_logs_trigger_type', table_name='audit_logs')
    op.drop_column('audit_logs', 'confidence_metadata')
    op.drop_column('audit_logs', 'trigger_type')
    op.execute("DROP TYPE IF EXISTS audittriggertype")
