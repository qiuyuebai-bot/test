"""add issued tutoring questions

Revision ID: c4d2e8f1a7b3
Revises: a3f7c2e8b4d1
Create Date: 2026-07-28 17:05:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c4d2e8f1a7b3"
down_revision: Union[str, None] = "a3f7c2e8b4d1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "issued_tutoring_questions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("learner_id", sa.Integer(), sa.ForeignKey("learner_profiles.id"), nullable=False),
        sa.Column("question_type", sa.String(length=30), nullable=False),
        sa.Column("topic", sa.String(length=100), nullable=False),
        sa.Column("difficulty", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("options", sa.JSON(), nullable=False),
        sa.Column("answer_key", sa.JSON(), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("knowledge_points", sa.JSON(), nullable=True),
        sa.Column("source_slice_ids", sa.JSON(), nullable=True),
        sa.Column("source_doc_ids", sa.JSON(), nullable=True),
        sa.Column("generation_method", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("answered_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_issued_tutoring_questions_user_id", "issued_tutoring_questions", ["user_id"])
    op.create_index("ix_issued_tutoring_questions_learner_id", "issued_tutoring_questions", ["learner_id"])
    op.create_index("ix_issued_tutoring_questions_topic", "issued_tutoring_questions", ["topic"])
    op.create_index("ix_issued_tutoring_questions_status", "issued_tutoring_questions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_issued_tutoring_questions_status", table_name="issued_tutoring_questions")
    op.drop_index("ix_issued_tutoring_questions_topic", table_name="issued_tutoring_questions")
    op.drop_index("ix_issued_tutoring_questions_learner_id", table_name="issued_tutoring_questions")
    op.drop_index("ix_issued_tutoring_questions_user_id", table_name="issued_tutoring_questions")
    op.drop_table("issued_tutoring_questions")
