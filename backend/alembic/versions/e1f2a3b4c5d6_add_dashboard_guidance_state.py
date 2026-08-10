"""add dashboard guidance state

Revision ID: e1f2a3b4c5d6
Revises: d8e3f4a5b6c7
Create Date: 2026-08-10 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e1f2a3b4c5d6"
down_revision: Union[str, None] = "d8e3f4a5b6c7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("dashboard_guidance_states"):
        return

    op.create_table(
        "dashboard_guidance_states",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("onboarding_completed_at", sa.DateTime(), nullable=True),
        sa.Column("dashboard_guidance_dismissed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("user_id", name="uq_dashboard_guidance_state_user"),
    )
    op.create_index(
        "ix_dashboard_guidance_states_user_id",
        "dashboard_guidance_states",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_dashboard_guidance_states_user_id", table_name="dashboard_guidance_states")
    op.drop_table("dashboard_guidance_states")
