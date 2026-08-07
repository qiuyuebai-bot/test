"""add issued question source traceability

Revision ID: d8e3f4a5b6c7
Revises: c4d2e8f1a7b3
Create Date: 2026-08-03 12:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d8e3f4a5b6c7"
down_revision: Union[str, None] = "c4d2e8f1a7b3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    issued_columns = {column["name"] for column in inspector.get_columns("issued_tutoring_questions")}
    issued_indexes = {index["name"] for index in inspector.get_indexes("issued_tutoring_questions")}
    issued_uniques = {constraint["name"] for constraint in inspector.get_unique_constraints("issued_tutoring_questions")}
    if (
        "source_resource_id" not in issued_columns
        or "source_question_index" not in issued_columns
        or "ix_issued_tutoring_questions_source_resource_id" not in issued_indexes
        or "uq_issued_question_source_index" not in issued_uniques
    ):
        with op.batch_alter_table("issued_tutoring_questions") as batch_op:
            if "source_resource_id" not in issued_columns:
                batch_op.add_column(
                    sa.Column(
                        "source_resource_id",
                        sa.Integer(),
                        sa.ForeignKey("learning_resources.id", name="fk_issued_question_source_resource"),
                        nullable=True,
                    ),
                )
            if "source_question_index" not in issued_columns:
                batch_op.add_column(sa.Column("source_question_index", sa.Integer(), nullable=True))
            if "ix_issued_tutoring_questions_source_resource_id" not in issued_indexes:
                batch_op.create_index("ix_issued_tutoring_questions_source_resource_id", ["source_resource_id"])
            if "uq_issued_question_source_index" not in issued_uniques:
                batch_op.create_unique_constraint(
                    "uq_issued_question_source_index",
                    ["source_resource_id", "source_question_index"],
                )

    answer_columns = {column["name"] for column in inspector.get_columns("answer_records")}
    answer_indexes = {index["name"] for index in inspector.get_indexes("answer_records")}
    answer_uniques = {constraint["name"] for constraint in inspector.get_unique_constraints("answer_records")}
    if (
        "issued_question_id" not in answer_columns
        or "ix_answer_records_issued_question_id" not in answer_indexes
        or "uq_answer_record_issued_question" not in answer_uniques
    ):
        with op.batch_alter_table("answer_records") as batch_op:
            if "issued_question_id" not in answer_columns:
                batch_op.add_column(
                    sa.Column(
                        "issued_question_id",
                        sa.Integer(),
                        sa.ForeignKey("issued_tutoring_questions.id", name="fk_answer_record_issued_question"),
                        nullable=True,
                    ),
                )
            if "ix_answer_records_issued_question_id" not in answer_indexes:
                batch_op.create_index("ix_answer_records_issued_question_id", ["issued_question_id"])
            if "uq_answer_record_issued_question" not in answer_uniques:
                batch_op.create_unique_constraint(
                    "uq_answer_record_issued_question",
                    ["issued_question_id"],
                )

    # Keep the canonical first result for historical retry duplicates so the
    # new uniqueness guarantee does not block upgrades on existing data.
    op.execute(
        """
        UPDATE learning_resources
        SET generation_task_id = NULL
        WHERE generation_task_id IS NOT NULL
          AND id NOT IN (
            SELECT MIN(id)
            FROM learning_resources
            WHERE generation_task_id IS NOT NULL
            GROUP BY generation_task_id
          )
        """
    )
    resource_uniques = {constraint["name"] for constraint in inspector.get_unique_constraints("learning_resources")}
    if "uq_learning_resource_generation_task" not in resource_uniques:
        with op.batch_alter_table("learning_resources") as batch_op:
            batch_op.create_unique_constraint(
                "uq_learning_resource_generation_task",
                ["generation_task_id"],
            )


def downgrade() -> None:
    with op.batch_alter_table("learning_resources") as batch_op:
        batch_op.drop_constraint("uq_learning_resource_generation_task", type_="unique")

    with op.batch_alter_table("answer_records") as batch_op:
        batch_op.drop_constraint("uq_answer_record_issued_question", type_="unique")
        batch_op.drop_index("ix_answer_records_issued_question_id")
        batch_op.drop_column("issued_question_id")

    with op.batch_alter_table("issued_tutoring_questions") as batch_op:
        batch_op.drop_constraint("uq_issued_question_source_index", type_="unique")
        batch_op.drop_index("ix_issued_tutoring_questions_source_resource_id")
        batch_op.drop_column("source_question_index")
        batch_op.drop_column("source_resource_id")
