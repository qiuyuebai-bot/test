"""initial schema

Revision ID: 8455fe7f1990
Revises: 
Create Date: 2026-07-05 20:53:57.430775

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8455fe7f1990'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 空迁移：表结构由 Base.metadata.create_all 创建（已存在）
    # 此迁移仅用于建立 alembic 版本基线，便于后续增量迁移
    pass


def downgrade() -> None:
    # 不删除任何表（避免数据丢失）
    pass
