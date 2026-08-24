"""add generated lecture knowledge publication workflow

Revision ID: a7b8c9d0e1f2
Revises: f9a6b7c8d9e0
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "a7b8c9d0e1f2"
down_revision: Union[str, None] = "f9a6b7c8d9e0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("knowledge_docs"):
        columns = {item["name"] for item in inspector.get_columns("knowledge_docs")}
        indexes = {item["name"] for item in inspector.get_indexes("knowledge_docs")}
        if (
            "origin_type" not in columns
            or "origin_resource_id" not in columns
            or "ix_knowledge_docs_origin_type" not in indexes
            or "ix_knowledge_docs_origin_resource_id" not in indexes
        ):
            with op.batch_alter_table("knowledge_docs") as batch_op:
                if "origin_type" not in columns:
                    batch_op.add_column(sa.Column("origin_type", sa.String(length=50), nullable=True))
                if "origin_resource_id" not in columns:
                    batch_op.add_column(
                        sa.Column(
                            "origin_resource_id",
                            sa.Integer(),
                            sa.ForeignKey("learning_resources.id", name="fk_knowledge_docs_origin_resource"),
                            nullable=True,
                        )
                    )
                if "ix_knowledge_docs_origin_type" not in indexes:
                    batch_op.create_index("ix_knowledge_docs_origin_type", ["origin_type"])
                if "ix_knowledge_docs_origin_resource_id" not in indexes:
                    batch_op.create_index("ix_knowledge_docs_origin_resource_id", ["origin_resource_id"])

    if not inspector.has_table("knowledge_publication_requests"):
        op.create_table(
            "knowledge_publication_requests",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("resource_id", sa.Integer(), sa.ForeignKey("learning_resources.id"), nullable=False),
            sa.Column("resource_version", sa.String(length=20), nullable=False),
            sa.Column("content_hash", sa.String(length=64), nullable=False),
            sa.Column("snapshot", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
            sa.Column("submitted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("reviewed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("review_note", sa.Text(), nullable=True),
            sa.Column("knowledge_doc_id", sa.Integer(), sa.ForeignKey("knowledge_docs.id"), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("submitted_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
            sa.Column("reviewed_at", sa.DateTime(), nullable=True),
            sa.Column("published_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        )
        op.create_index("ix_knowledge_publication_requests_resource_id", "knowledge_publication_requests", ["resource_id"])
        op.create_index("ix_knowledge_publication_requests_status", "knowledge_publication_requests", ["status"])
        op.create_index("ix_knowledge_publication_requests_knowledge_doc_id", "knowledge_publication_requests", ["knowledge_doc_id"])
        op.create_index("ix_knowledge_publication_requests_resource_status", "knowledge_publication_requests", ["resource_id", "status"])
        op.create_index("ix_knowledge_publication_requests_submitted_by", "knowledge_publication_requests", ["submitted_by"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("knowledge_publication_requests"):
        for index_name in (
            "ix_knowledge_publication_requests_submitted_by",
            "ix_knowledge_publication_requests_resource_status",
            "ix_knowledge_publication_requests_knowledge_doc_id",
            "ix_knowledge_publication_requests_status",
            "ix_knowledge_publication_requests_resource_id",
        ):
            op.drop_index(index_name, table_name="knowledge_publication_requests")
        op.drop_table("knowledge_publication_requests")
    if inspector.has_table("knowledge_docs"):
        indexes = {item["name"] for item in sa.inspect(bind).get_indexes("knowledge_docs")}
        columns = {item["name"] for item in sa.inspect(bind).get_columns("knowledge_docs")}
        if (
            "ix_knowledge_docs_origin_resource_id" in indexes
            or "ix_knowledge_docs_origin_type" in indexes
            or "origin_resource_id" in columns
            or "origin_type" in columns
        ):
            with op.batch_alter_table("knowledge_docs") as batch_op:
                if "ix_knowledge_docs_origin_resource_id" in indexes:
                    batch_op.drop_index("ix_knowledge_docs_origin_resource_id")
                if "ix_knowledge_docs_origin_type" in indexes:
                    batch_op.drop_index("ix_knowledge_docs_origin_type")
                if "origin_resource_id" in columns:
                    batch_op.drop_column("origin_resource_id")
                if "origin_type" in columns:
                    batch_op.drop_column("origin_type")
