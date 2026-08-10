"""add learner diagnostic state

Revision ID: f2a4b6c8d0e1
Revises: e1f2a3b4c5d6
Create Date: 2026-08-10 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a4b6c8d0e1"
down_revision: Union[str, None] = "e1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_if_missing(bind, table: str, column: sa.Column) -> None:
    inspector = sa.inspect(bind)
    existing = {item["name"] for item in inspector.get_columns(table)}
    if column.name not in existing:
        op.add_column(table, column)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    _add_column_if_missing(
        bind,
        "learner_profiles",
        sa.Column("ability_assessments", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )
    _add_column_if_missing(
        bind,
        "learner_profiles",
        sa.Column("diagnostic_status", sa.String(length=20), nullable=False, server_default="not_started"),
    )
    _add_column_if_missing(
        bind,
        "learner_profiles",
        sa.Column("diagnostic_completed_at", sa.DateTime(), nullable=True),
    )

    if not inspector.has_table("diagnostic_sessions"):
        op.create_table(
            "diagnostic_sessions",
            sa.Column("id", sa.String(length=64), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("learner_id", sa.Integer(), sa.ForeignKey("learner_profiles.id"), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="active"),
            sa.Column("questions_per_dimension", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("total_questions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("answered_questions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("dimension_counts", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("results", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("completed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_diagnostic_sessions_user_id", "diagnostic_sessions", ["user_id"])
        op.create_index("ix_diagnostic_sessions_learner_id", "diagnostic_sessions", ["learner_id"])
        op.create_index("ix_diagnostic_sessions_status", "diagnostic_sessions", ["status"])

    issued_columns = {item["name"] for item in sa.inspect(bind).get_columns("issued_tutoring_questions")}
    if "assessment_mode" not in issued_columns:
        op.add_column(
            "issued_tutoring_questions",
            sa.Column("assessment_mode", sa.String(length=20), nullable=False, server_default="practice"),
        )
        op.create_index(
            "ix_issued_tutoring_questions_assessment_mode",
            "issued_tutoring_questions",
            ["assessment_mode"],
        )
    if "ability_dimension" not in issued_columns:
        op.add_column(
            "issued_tutoring_questions",
            sa.Column("ability_dimension", sa.String(length=50), nullable=True),
        )
        op.create_index(
            "ix_issued_tutoring_questions_ability_dimension",
            "issued_tutoring_questions",
            ["ability_dimension"],
        )
    if "diagnostic_session_id" not in issued_columns:
        op.add_column(
            "issued_tutoring_questions",
            sa.Column(
                "diagnostic_session_id",
                sa.String(length=64),
                nullable=True,
            ),
        )
        op.create_index(
            "ix_issued_tutoring_questions_diagnostic_session_id",
            "issued_tutoring_questions",
            ["diagnostic_session_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_issued_tutoring_questions_diagnostic_session_id", table_name="issued_tutoring_questions")
    op.drop_column("issued_tutoring_questions", "diagnostic_session_id")
    op.drop_index("ix_issued_tutoring_questions_ability_dimension", table_name="issued_tutoring_questions")
    op.drop_column("issued_tutoring_questions", "ability_dimension")
    op.drop_index("ix_issued_tutoring_questions_assessment_mode", table_name="issued_tutoring_questions")
    op.drop_column("issued_tutoring_questions", "assessment_mode")
    op.drop_index("ix_diagnostic_sessions_status", table_name="diagnostic_sessions")
    op.drop_index("ix_diagnostic_sessions_learner_id", table_name="diagnostic_sessions")
    op.drop_index("ix_diagnostic_sessions_user_id", table_name="diagnostic_sessions")
    op.drop_table("diagnostic_sessions")
    op.drop_column("learner_profiles", "diagnostic_completed_at")
    op.drop_column("learner_profiles", "diagnostic_status")
    op.drop_column("learner_profiles", "ability_assessments")
