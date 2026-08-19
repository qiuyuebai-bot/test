"""add certification domain tables

Revision ID: 1de390ec478a
Revises: b560a55bf539
Create Date: 2026-08-11 19:36:35.869871

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '1de390ec478a'
down_revision: Union[str, None] = 'b560a55bf539'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    # Preserve schemas created by the legacy create_all-before-Alembic startup.
    if all(inspector.has_table(table) for table in (
        'certifications', 'certification_rules', 'certification_records'
    )):
        return

    # 认证定义表
    op.create_table('certifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='认证ID'),
        sa.Column('position_id', sa.Integer(), nullable=False, comment='关联岗位ID'),
        sa.Column('name', sa.String(length=200), nullable=False, comment='认证名称'),
        sa.Column('code', sa.String(length=50), nullable=False, comment='认证编码'),
        sa.Column('level', sa.String(length=20), nullable=True, comment='认证级别'),
        sa.Column('description', sa.Text(), nullable=True, comment='认证描述'),
        sa.Column('validity_period_months', sa.Integer(), nullable=True, comment='有效期(月)'),
        sa.Column('issuer', sa.String(length=100), nullable=True, comment='发证机构'),
        sa.Column('is_active', sa.Boolean(), nullable=True, comment='是否启用'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='更新时间'),
        sa.ForeignKeyConstraint(['position_id'], ['positions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_certifications_position_id'), 'certifications', ['position_id'], unique=False)
    op.create_index(op.f('ix_certifications_code'), 'certifications', ['code'], unique=True)

    # 发证规则表
    op.create_table('certification_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='规则ID'),
        sa.Column('certification_id', sa.Integer(), nullable=False, comment='认证ID'),
        sa.Column('rule_type', sa.String(length=30), nullable=False, comment='规则类型'),
        sa.Column('rule_config', sa.JSON(), nullable=True, comment='规则配置'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='创建时间'),
        sa.ForeignKeyConstraint(['certification_id'], ['certifications.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_certification_rules_certification_id'), 'certification_rules', ['certification_id'], unique=False)

    # 认证记录表
    op.create_table('certification_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='记录ID'),
        sa.Column('certification_id', sa.Integer(), nullable=False, comment='认证ID'),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='用户ID'),
        sa.Column('learner_id', sa.Integer(), nullable=True, comment='学习者画像ID'),
        sa.Column('assessment_record_id', sa.Integer(), nullable=False, comment='关联评估记录ID'),
        sa.Column('status', sa.String(length=20), nullable=True, comment='认证状态'),
        sa.Column('certificate_number', sa.String(length=100), nullable=True, comment='证书编号'),
        sa.Column('rule_evaluation', sa.JSON(), nullable=True, comment='规则评估结果'),
        sa.Column('issued_at', sa.DateTime(), nullable=True, comment='发证时间'),
        sa.Column('expires_at', sa.DateTime(), nullable=True, comment='过期时间'),
        sa.Column('reviewed_by', sa.Integer(), nullable=True, comment='审核人ID'),
        sa.Column('review_comment', sa.Text(), nullable=True, comment='审核意见'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='更新时间'),
        sa.ForeignKeyConstraint(['assessment_record_id'], ['assessment_records.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['certification_id'], ['certifications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['learner_id'], ['learner_profiles.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_certification_records_assessment_record_id'), 'certification_records', ['assessment_record_id'], unique=False)
    op.create_index(op.f('ix_certification_records_certification_id'), 'certification_records', ['certification_id'], unique=False)
    op.create_index(op.f('ix_certification_records_user_id'), 'certification_records', ['user_id'], unique=False)
    op.create_index(op.f('ix_certification_records_learner_id'), 'certification_records', ['learner_id'], unique=False)
    op.create_index(op.f('ix_certification_records_certificate_number'), 'certification_records', ['certificate_number'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_certification_records_certificate_number'), table_name='certification_records')
    op.drop_index(op.f('ix_certification_records_learner_id'), table_name='certification_records')
    op.drop_index(op.f('ix_certification_records_user_id'), table_name='certification_records')
    op.drop_index(op.f('ix_certification_records_certification_id'), table_name='certification_records')
    op.drop_index(op.f('ix_certification_records_assessment_record_id'), table_name='certification_records')
    op.drop_table('certification_records')
    op.drop_index(op.f('ix_certification_rules_certification_id'), table_name='certification_rules')
    op.drop_table('certification_rules')
    op.drop_index(op.f('ix_certifications_code'), table_name='certifications')
    op.drop_index(op.f('ix_certifications_position_id'), table_name='certifications')
    op.drop_table('certifications')
