"""add per-user AI configuration

Revision ID: c1d2e3f4a5b6
Revises: b1c2d3e4f5a6
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if sa.inspect(bind).has_table("user_ai_configs"):
        return

    op.create_table(
        "user_ai_configs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False, server_default="custom"),
        sa.Column("protocol", sa.String(length=64), nullable=False, server_default="openai_chat"),
        sa.Column("base_url", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("api_key_encrypted", sa.Text(), nullable=True),
        sa.Column("selected_model", sa.String(length=255), nullable=True),
        sa.Column("available_models", sa.JSON(), nullable=False),
        sa.Column("proxy_url", sa.String(length=500), nullable=True, server_default=""),
        sa.Column("proxy_password_encrypted", sa.Text(), nullable=True),
        sa.Column("extra_config", sa.JSON(), nullable=False),
        sa.Column("last_test_status", sa.String(length=32), nullable=False, server_default="never"),
        sa.Column("last_test_message", sa.String(length=500), nullable=True),
        sa.Column("last_tested_at", sa.DateTime(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("user_id", name="uq_user_ai_configs_user_id"),
    )
    op.create_index("ix_user_ai_configs_user_id", "user_ai_configs", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("user_ai_configs"):
        return
    op.drop_index("ix_user_ai_configs_user_id", table_name="user_ai_configs")
    op.drop_table("user_ai_configs")
