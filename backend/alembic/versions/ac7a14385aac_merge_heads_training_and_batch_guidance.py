"""merge heads training and batch guidance

Revision ID: ac7a14385aac
Revises: 5d4191d5dab0, b7c9d1e3f5a7
Create Date: 2026-08-12 12:53:31.081521

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ac7a14385aac'
down_revision: Union[str, None] = ('5d4191d5dab0', 'b7c9d1e3f5a7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
