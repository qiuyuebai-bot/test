"""add batch guidance session metadata and idempotent results"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b7c9d1e3f5a7"
down_revision: Union[str, None] = "f2a4b6c8d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    issued_columns = {column["name"] for column in inspector.get_columns("issued_tutoring_questions")}
    issued_indexes = {index["name"] for index in inspector.get_indexes("issued_tutoring_questions")}
    if "session_id" not in issued_columns:
        with op.batch_alter_table("issued_tutoring_questions") as batch_op:
            batch_op.add_column(sa.Column("session_id", sa.String(length=100), nullable=True))
    if "ix_issued_tutoring_questions_session_id" not in issued_indexes:
        op.create_index(
            "ix_issued_tutoring_questions_session_id",
            "issued_tutoring_questions",
            ["session_id"],
        )

    if not inspector.has_table("batch_tutoring_submissions"):
        op.create_table(
            "batch_tutoring_submissions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("learner_id", sa.Integer(), sa.ForeignKey("learner_profiles.id"), nullable=False),
            sa.Column("session_id", sa.String(length=100), nullable=False),
            sa.Column("answer_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("result_summary", sa.JSON(), nullable=False),
            sa.Column("submitted_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.UniqueConstraint(
                "user_id",
                "learner_id",
                "session_id",
                name="uq_batch_tutoring_submission_session",
            ),
        )
        op.create_index("ix_batch_tutoring_submissions_user_id", "batch_tutoring_submissions", ["user_id"])
        op.create_index("ix_batch_tutoring_submissions_learner_id", "batch_tutoring_submissions", ["learner_id"])
        op.create_index("ix_batch_tutoring_submissions_session_id", "batch_tutoring_submissions", ["session_id"])


def downgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table("batch_tutoring_submissions"):
        op.drop_index("ix_batch_tutoring_submissions_session_id", table_name="batch_tutoring_submissions")
        op.drop_index("ix_batch_tutoring_submissions_learner_id", table_name="batch_tutoring_submissions")
        op.drop_index("ix_batch_tutoring_submissions_user_id", table_name="batch_tutoring_submissions")
        op.drop_table("batch_tutoring_submissions")
    issued_columns = {column["name"] for column in inspector.get_columns("issued_tutoring_questions")}
    if "session_id" in issued_columns:
        with op.batch_alter_table("issued_tutoring_questions") as batch_op:
            batch_op.drop_index("ix_issued_tutoring_questions_session_id")
            batch_op.drop_column("session_id")
