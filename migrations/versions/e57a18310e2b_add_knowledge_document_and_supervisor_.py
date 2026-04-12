"""add knowledge_document and supervisor_decision tables

Revision ID: e57a18310e2b
Revises: 7535a0e6314f
Create Date: 2026-04-12 03:40:24.974380

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision: str = "e57a18310e2b"
down_revision: Union[str, None] = "7535a0e6314f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("filename", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("storage_path", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("content_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("doc_size_bytes", sa.Integer(), nullable=True),
        sa.Column("sync_status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("sync_message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_knowledge_documents_filename"), "knowledge_documents", ["filename"], unique=False
    )
    op.create_table(
        "supervisor_decisions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column("primary_intent", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True),
        sa.Column("pending_intents", sqlmodel.sql.sqltypes.AutoString(length=256), nullable=True),
        sa.Column("selected_agents", sqlmodel.sql.sqltypes.AutoString(length=256), nullable=True),
        sa.Column("execution_mode", sqlmodel.sql.sqltypes.AutoString(length=16), nullable=True),
        sa.Column("reasoning", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_supervisor_decisions_thread_id"),
        "supervisor_decisions",
        ["thread_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_supervisor_decisions_thread_id"), table_name="supervisor_decisions")
    op.drop_table("supervisor_decisions")
    op.drop_index(op.f("ix_knowledge_documents_filename"), table_name="knowledge_documents")
    op.drop_table("knowledge_documents")
