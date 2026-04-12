"""add_phase4_complaint_experiment_evaluation_models

Revision ID: 053eaa2f0a66
Revises: 5cc243312e9f
Create Date: 2026-04-12 19:31:11.944703

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "053eaa2f0a66"
down_revision: Union[str, None] = "5cc243312e9f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Phase 4 new tables
    op.create_table(
        "complaint_tickets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column("category", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("order_sn", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column(
            "expected_resolution", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False
        ),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("assigned_to", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_complaint_tickets_assigned_to"), "complaint_tickets", ["assigned_to"], unique=False
    )
    op.create_index(
        op.f("ix_complaint_tickets_thread_id"), "complaint_tickets", ["thread_id"], unique=False
    )
    op.create_index(
        op.f("ix_complaint_tickets_user_id"), "complaint_tickets", ["user_id"], unique=False
    )

    op.create_table(
        "experiments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column("target_dimensions", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "experiment_variants",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("experiment_id", sa.Integer(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False),
        sa.Column("system_prompt", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("llm_model", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True),
        sa.Column("retriever_top_k", sa.Integer(), nullable=True),
        sa.Column("reranker_enabled", sa.Boolean(), nullable=True),
        sa.Column("extra_config", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["experiment_id"],
            ["experiments.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_experiment_variants_experiment_id"),
        "experiment_variants",
        ["experiment_id"],
        unique=False,
    )

    op.create_table(
        "experiment_assignments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("experiment_id", sa.Integer(), nullable=False),
        sa.Column("variant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["experiment_id"],
            ["experiments.id"],
        ),
        sa.ForeignKeyConstraint(
            ["variant_id"],
            ["experiment_variants.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_experiment_assignments_experiment_id"),
        "experiment_assignments",
        ["experiment_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_experiment_assignments_user_id"),
        "experiment_assignments",
        ["user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_experiment_assignments_variant_id"),
        "experiment_assignments",
        ["variant_id"],
        unique=False,
    )

    op.create_table(
        "message_feedbacks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("thread_id", sqlmodel.sql.sqltypes.AutoString(length=128), nullable=False),
        sa.Column("message_index", sa.Integer(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("comment", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_message_feedbacks_thread_id"), "message_feedbacks", ["thread_id"], unique=False
    )
    op.create_index(
        op.f("ix_message_feedbacks_user_id"), "message_feedbacks", ["user_id"], unique=False
    )

    op.create_table(
        "quality_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("score_date", sa.Date(), nullable=False),
        sa.Column("total_sessions", sa.Integer(), nullable=False),
        sa.Column("human_transfer_rate", sa.Float(), nullable=True),
        sa.Column("avg_confidence", sa.Float(), nullable=True),
        sa.Column("avg_turns", sa.Float(), nullable=True),
        sa.Column("implicit_satisfaction_rate", sa.Float(), nullable=True),
        sa.Column("explicit_upvotes", sa.Integer(), nullable=False),
        sa.Column("explicit_downvotes", sa.Integer(), nullable=False),
        sa.Column("immediate_transfer_count", sa.Integer(), nullable=False),
        sa.Column("contradictory_followup_count", sa.Integer(), nullable=False),
        sa.Column("low_confidence_retry_count", sa.Integer(), nullable=False),
        sa.Column("intent_breakdown", sa.JSON(), nullable=True),
        sa.Column("top_degraded_intents", sa.JSON(), nullable=True),
        sa.Column("sample_trace_ids", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_quality_scores_score_date"), "quality_scores", ["score_date"], unique=False
    )

    # Add langsmith_run_url to existing graph_execution_logs
    op.add_column(
        "graph_execution_logs",
        sa.Column("langsmith_run_url", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("graph_execution_logs", "langsmith_run_url")

    op.drop_index(op.f("ix_quality_scores_score_date"), table_name="quality_scores")
    op.drop_table("quality_scores")
    op.drop_index(op.f("ix_message_feedbacks_user_id"), table_name="message_feedbacks")
    op.drop_index(op.f("ix_message_feedbacks_thread_id"), table_name="message_feedbacks")
    op.drop_table("message_feedbacks")
    op.drop_index(op.f("ix_experiment_assignments_variant_id"), table_name="experiment_assignments")
    op.drop_index(op.f("ix_experiment_assignments_user_id"), table_name="experiment_assignments")
    op.drop_index(
        op.f("ix_experiment_assignments_experiment_id"), table_name="experiment_assignments"
    )
    op.drop_table("experiment_assignments")
    op.drop_index(op.f("ix_experiment_variants_experiment_id"), table_name="experiment_variants")
    op.drop_table("experiment_variants")
    op.drop_table("experiments")
    op.drop_index(op.f("ix_complaint_tickets_user_id"), table_name="complaint_tickets")
    op.drop_index(op.f("ix_complaint_tickets_thread_id"), table_name="complaint_tickets")
    op.drop_index(op.f("ix_complaint_tickets_assigned_to"), table_name="complaint_tickets")
    op.drop_table("complaint_tickets")
