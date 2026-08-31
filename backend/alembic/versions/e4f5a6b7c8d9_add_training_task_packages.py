"""add structured training task packages and submissions"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, None] = "d2e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("positions") and "key_tasks" not in {column["name"] for column in inspector.get_columns("positions")}: 
        op.add_column("positions", sa.Column("key_tasks", sa.JSON(), nullable=True, comment="关键任务列表"))

    if not inspector.has_table("training_task_packages"):
        op.create_table(
            "training_task_packages",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("sequence", sa.Integer(), nullable=True),
            sa.Column("task_type", sa.String(30), nullable=True),
            sa.Column("key_task_code", sa.String(80), nullable=True),
            sa.Column("learning_objectives", sa.JSON(), nullable=True),
            sa.Column("resources", sa.JSON(), nullable=True),
            sa.Column("submission_required", sa.Boolean(), nullable=True),
            sa.Column("passing_score", sa.Float(), nullable=True),
            sa.Column("is_mandatory", sa.Boolean(), nullable=True),
            sa.Column("status", sa.String(20), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)")),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)")),
            sa.ForeignKeyConstraint(["project_id"], ["training_projects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        )
        op.create_index("ix_training_task_packages_project_id", "training_task_packages", ["project_id"])

    if not inspector.has_table("training_task_rubrics"):
        op.create_table(
            "training_task_rubrics",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("task_package_id", sa.Integer(), nullable=False),
            sa.Column("criterion", sa.String(200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("max_score", sa.Float(), nullable=True),
            sa.Column("weight", sa.Float(), nullable=True),
            sa.Column("sequence", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)")),
            sa.ForeignKeyConstraint(["task_package_id"], ["training_task_packages.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_training_task_rubrics_task_package_id", "training_task_rubrics", ["task_package_id"])

    if not inspector.has_table("training_submissions"):
        op.create_table(
            "training_submissions",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("task_package_id", sa.Integer(), nullable=False),
            sa.Column("enrollment_id", sa.Integer(), nullable=False),
            sa.Column("learner_id", sa.Integer(), nullable=True),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("attempt_number", sa.Integer(), nullable=True),
            sa.Column("content", sa.Text(), nullable=True),
            sa.Column("attachments", sa.JSON(), nullable=True),
            sa.Column("demo_url", sa.String(500), nullable=True),
            sa.Column("status", sa.String(20), nullable=True),
            sa.Column("overall_score", sa.Float(), nullable=True),
            sa.Column("teacher_comment", sa.Text(), nullable=True),
            sa.Column("reviewed_by", sa.Integer(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)")),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)")),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)")),
            sa.ForeignKeyConstraint(["task_package_id"], ["training_task_packages.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["enrollment_id"], ["training_enrollments.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["learner_id"], ["learner_profiles.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        )
        for column in ("task_package_id", "enrollment_id", "learner_id", "user_id"):
            op.create_index(f"ix_training_submissions_{column}", "training_submissions", [column])

    if not inspector.has_table("training_submission_scores"):
        op.create_table(
            "training_submission_scores",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("submission_id", sa.Integer(), nullable=False),
            sa.Column("rubric_id", sa.Integer(), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("comment", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)")),
            sa.ForeignKeyConstraint(["submission_id"], ["training_submissions.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["rubric_id"], ["training_task_rubrics.id"], ondelete="CASCADE"),
        )
        op.create_index("ix_training_submission_scores_submission_id", "training_submission_scores", ["submission_id"])
        op.create_index("ix_training_submission_scores_rubric_id", "training_submission_scores", ["rubric_id"])


def downgrade() -> None:
    op.drop_index("ix_training_submission_scores_rubric_id", table_name="training_submission_scores")
    op.drop_index("ix_training_submission_scores_submission_id", table_name="training_submission_scores")
    op.drop_table("training_submission_scores")
    for column in ("task_package_id", "enrollment_id", "learner_id", "user_id"):
        op.drop_index(f"ix_training_submissions_{column}", table_name="training_submissions")
    op.drop_table("training_submissions")
    op.drop_index("ix_training_task_rubrics_task_package_id", table_name="training_task_rubrics")
    op.drop_table("training_task_rubrics")
    op.drop_index("ix_training_task_packages_project_id", table_name="training_task_packages")
    op.drop_table("training_task_packages")
    op.drop_column("positions", "key_tasks")
