"""add_multi_intent_decision_log_and_graph_execution_version_id

Revision ID: 46240a43ccc7
Revises: ad240cc404ba
Create Date: 2026-04-16 23:48:50.816537

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision: str = "46240a43ccc7"
down_revision: Union[str, None] = "ad240cc404ba"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "multi_intent_decision_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("query", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("intent_a", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("intent_b", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("rule_based_result", sa.Boolean(), nullable=True),
        sa.Column("llm_result", sa.Boolean(), nullable=True),
        sa.Column("llm_reason", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("human_label", sa.Boolean(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.add_column(
        "graph_execution_logs", sa.Column("agent_config_version_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        op.f("fk_graph_execution_logs_agent_config_version_id_agent_config_versions"),
        "graph_execution_logs",
        "agent_config_versions",
        ["agent_config_version_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        op.f("fk_graph_execution_logs_agent_config_version_id_agent_config_versions"),
        "graph_execution_logs",
        type_="foreignkey",
    )
    op.drop_column("graph_execution_logs", "agent_config_version_id")
    op.drop_table("multi_intent_decision_logs")
