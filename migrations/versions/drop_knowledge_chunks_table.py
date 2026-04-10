"""drop knowledge_chunks table

Revision ID: drop_knowledge_chunks_table
Revises: v4_2_confidence_trigger
Create Date: 2026-04-09
"""

from typing import Union

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision: str = "drop_knowledge_chunks_table"
down_revision: Union[str, None] = "v4_2_confidence_trigger"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.drop_index("ix_knowledge_chunks_source", table_name="knowledge_chunks")
    op.drop_index("ix_knowledge_chunks_is_active", table_name="knowledge_chunks")
    op.drop_index(
        "ix_knowledge_chunks_embedding",
        table_name="knowledge_chunks",
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
    )
    op.drop_table("knowledge_chunks")
    op.execute(sa.text("DROP EXTENSION IF EXISTS vector"))


def downgrade() -> None:
    op.create_table(
        "knowledge_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", sa.Text(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("meta_data", sa.JSON(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_knowledge_chunks_source", "knowledge_chunks", ["source"], unique=False)
    op.create_index(
        "ix_knowledge_chunks_is_active", "knowledge_chunks", ["is_active"], unique=False
    )
    op.create_index(
        "ix_knowledge_chunks_embedding",
        "knowledge_chunks",
        [sa.literal_column("embedding vector_cosine_ops")],
        unique=False,
        postgresql_using="hnsw",
        postgresql_with={"m": 16, "ef_construction": 64},
    )
    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS vector"))
