"""add review status to generated learning resources

Revision ID: b1c2d3e4f5a6
Revises: a7b8c9d0e1f2
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("learning_resources"):
        return

    columns = {column["name"] for column in inspector.get_columns("learning_resources")}
    indexes = {index["name"] for index in inspector.get_indexes("learning_resources")}
    if "review_status" not in columns or "ix_learning_resources_review_status" not in indexes:
        with op.batch_alter_table("learning_resources") as batch_op:
            if "review_status" not in columns:
                batch_op.add_column(
                    sa.Column(
                        "review_status",
                        sa.String(length=20),
                        nullable=False,
                        server_default="pending",
                    )
                )
            if "ix_learning_resources_review_status" not in indexes:
                batch_op.create_index("ix_learning_resources_review_status", ["review_status"])

    resources = sa.table(
        "learning_resources",
        sa.column("review_status"),
        sa.column("status"),
        sa.column("validation_passed"),
    )
    op.execute(
        resources.update()
        .where(resources.c.status == "ready")
        .where(resources.c.validation_passed.is_(True))
        .where(resources.c.review_status == "pending")
        .values(review_status="approved")
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("learning_resources"):
        return

    columns = {column["name"] for column in inspector.get_columns("learning_resources")}
    indexes = {index["name"] for index in inspector.get_indexes("learning_resources")}
    if "review_status" in columns or "ix_learning_resources_review_status" in indexes:
        with op.batch_alter_table("learning_resources") as batch_op:
            if "ix_learning_resources_review_status" in indexes:
                batch_op.drop_index("ix_learning_resources_review_status")
            if "review_status" in columns:
                batch_op.drop_column("review_status")
