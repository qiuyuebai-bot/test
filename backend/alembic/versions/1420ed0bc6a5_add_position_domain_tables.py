"""add position domain tables

Revision ID: 1420ed0bc6a5
Revises: d8e3f4a5b6c7
Create Date: 2026-08-11 12:14:01.782500

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1420ed0bc6a5'
down_revision: Union[str, None] = 'd8e3f4a5b6c7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    # Older startup code ran create_all before recording this revision. Keep
    # that complete schema and allow Alembic to advance the version table.
    if all(inspector.has_table(table) for table in (
        'competencies', 'positions', 'position_competencies'
    )):
        return

    # 岗位与胜任力域：创建 positions、competencies、position_competencies 三张表
    op.create_table('competencies',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='胜任力ID'),
    sa.Column('code', sa.String(length=50), nullable=False, comment='胜任力编码'),
    sa.Column('name', sa.String(length=100), nullable=False, comment='胜任力名称'),
    sa.Column('category', sa.String(length=50), nullable=True, comment='胜任力类别'),
    sa.Column('description', sa.Text(), nullable=True, comment='胜任力描述'),
    sa.Column('level_descriptions', sa.JSON(), nullable=True, comment='各等级描述'),
    sa.Column('is_active', sa.Boolean(), nullable=True, comment='是否启用'),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='创建时间'),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='更新时间'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_competencies_category'), 'competencies', ['category'], unique=False)
    op.create_index(op.f('ix_competencies_code'), 'competencies', ['code'], unique=True)
    op.create_index(op.f('ix_competencies_name'), 'competencies', ['name'], unique=False)
    op.create_table('positions',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='岗位ID'),
    sa.Column('code', sa.String(length=50), nullable=False, comment='岗位编码'),
    sa.Column('name', sa.String(length=100), nullable=False, comment='岗位名称'),
    sa.Column('category', sa.String(length=50), nullable=True, comment='岗位类别'),
    sa.Column('industry', sa.String(length=50), nullable=True, comment='所属行业'),
    sa.Column('level', sa.String(length=20), nullable=True, comment='岗位层级'),
    sa.Column('description', sa.Text(), nullable=True, comment='岗位描述'),
    sa.Column('responsibilities', sa.JSON(), nullable=True, comment='岗位职责列表'),
    sa.Column('prerequisites', sa.JSON(), nullable=True, comment='前置要求'),
    sa.Column('career_path', sa.JSON(), nullable=True, comment='职业发展路径'),
    sa.Column('is_active', sa.Boolean(), nullable=True, comment='是否启用'),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='创建时间'),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='更新时间'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_positions_category'), 'positions', ['category'], unique=False)
    op.create_index(op.f('ix_positions_code'), 'positions', ['code'], unique=True)
    op.create_index(op.f('ix_positions_name'), 'positions', ['name'], unique=False)
    op.create_table('position_competencies',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='关联ID'),
    sa.Column('position_id', sa.Integer(), nullable=False, comment='岗位ID'),
    sa.Column('competency_id', sa.Integer(), nullable=False, comment='胜任力ID'),
    sa.Column('required_level', sa.Integer(), nullable=False, comment='要求等级(1-5)'),
    sa.Column('weight', sa.Float(), nullable=True, comment='权重'),
    sa.Column('is_mandatory', sa.Boolean(), nullable=True, comment='是否必修'),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='创建时间'),
    sa.ForeignKeyConstraint(['competency_id'], ['competencies.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['position_id'], ['positions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('position_id', 'competency_id', name='uq_position_competency')
    )
    op.create_index(op.f('ix_position_competencies_competency_id'), 'position_competencies', ['competency_id'], unique=False)
    op.create_index(op.f('ix_position_competencies_position_id'), 'position_competencies', ['position_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_position_competencies_position_id'), table_name='position_competencies')
    op.drop_index(op.f('ix_position_competencies_competency_id'), table_name='position_competencies')
    op.drop_table('position_competencies')
    op.drop_index(op.f('ix_positions_name'), table_name='positions')
    op.drop_index(op.f('ix_positions_code'), table_name='positions')
    op.drop_index(op.f('ix_positions_category'), table_name='positions')
    op.drop_table('positions')
    op.drop_index(op.f('ix_competencies_name'), table_name='competencies')
    op.drop_index(op.f('ix_competencies_code'), table_name='competencies')
    op.drop_index(op.f('ix_competencies_category'), table_name='competencies')
    op.drop_table('competencies')
