"""remove reversible anonymization payload columns

Revision ID: f9a6b7c8d9e0
Revises: ac7a14385aac
Create Date: 2026-08-18 22:00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "f9a6b7c8d9e0"
down_revision: Union[str, None] = "ac7a14385aac"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "anonymized_data" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("anonymized_data")}
    removable = [name for name in ("original_data_encrypted", "original_example") if name in columns]
    if not removable:
        return

    with op.batch_alter_table("anonymized_data") as batch_op:
        for name in removable:
            batch_op.drop_column(name)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "anonymized_data" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("anonymized_data")}
    with op.batch_alter_table("anonymized_data") as batch_op:
        if "original_data_encrypted" not in columns:
            batch_op.add_column(sa.Column("original_data_encrypted", sa.Text(), nullable=True))
        if "original_example" not in columns:
            batch_op.add_column(sa.Column("original_example", sa.String(length=100), nullable=True))
