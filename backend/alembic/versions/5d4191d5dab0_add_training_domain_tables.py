"""add training domain tables

Revision ID: 5d4191d5dab0
Revises: 1de390ec478a
Create Date: 2026-08-11 19:55:40.187425

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d4191d5dab0'
down_revision: Union[str, None] = '1de390ec478a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    # Preserve schemas created by the legacy create_all-before-Alembic startup.
    if all(inspector.has_table(table) for table in (
        'training_projects', 'training_enrollments', 'training_plans'
    )):
        return

    # 培训项目表
    op.create_table('training_projects',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='项目ID'),
    sa.Column('name', sa.String(length=200), nullable=False, comment='项目名称'),
    sa.Column('description', sa.Text(), nullable=True, comment='项目描述'),
    sa.Column('position_id', sa.Integer(), nullable=False, comment='关联岗位ID'),
    sa.Column('certification_id', sa.Integer(), nullable=True, comment='关联认证ID'),
    sa.Column('project_type', sa.String(length=20), nullable=True, comment='项目类型 onboard/transfer/upskill/compliance'),
    sa.Column('enterprise_name', sa.String(length=100), nullable=True, comment='所属企业'),
    sa.Column('status', sa.String(length=20), nullable=True, comment='项目状态'),
    sa.Column('start_date', sa.Date(), nullable=True, comment='开始日期'),
    sa.Column('end_date', sa.Date(), nullable=True, comment='结束日期'),
    sa.Column('config', sa.JSON(), nullable=True, comment='项目级配置'),
    sa.Column('created_by', sa.Integer(), nullable=True, comment='创建人ID'),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='创建时间'),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='更新时间'),
    sa.ForeignKeyConstraint(['certification_id'], ['certifications.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['position_id'], ['positions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_training_projects_certification_id'), 'training_projects', ['certification_id'], unique=False)
    op.create_index(op.f('ix_training_projects_position_id'), 'training_projects', ['position_id'], unique=False)

    # 培训报名表
    op.create_table('training_enrollments',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='报名ID'),
    sa.Column('project_id', sa.Integer(), nullable=False, comment='项目ID'),
    sa.Column('user_id', sa.Integer(), nullable=False, comment='用户ID'),
    sa.Column('learner_id', sa.Integer(), nullable=True, comment='学习者画像ID'),
    sa.Column('status', sa.String(length=20), nullable=True, comment='报名状态'),
    sa.Column('enrolled_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='报名时间'),
    sa.Column('completed_at', sa.DateTime(), nullable=True, comment='完成时间'),
    sa.Column('final_score', sa.Float(), nullable=True, comment='最终得分'),
    sa.Column('certification_record_id', sa.Integer(), nullable=True, comment='认证记录ID'),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='创建时间'),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='更新时间'),
    sa.ForeignKeyConstraint(['certification_record_id'], ['certification_records.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['learner_id'], ['learner_profiles.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['project_id'], ['training_projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('project_id', 'user_id', name='uq_project_user')
    )
    op.create_index(op.f('ix_training_enrollments_learner_id'), 'training_enrollments', ['learner_id'], unique=False)
    op.create_index(op.f('ix_training_enrollments_project_id'), 'training_enrollments', ['project_id'], unique=False)
    op.create_index(op.f('ix_training_enrollments_user_id'), 'training_enrollments', ['user_id'], unique=False)

    # 培训计划表
    op.create_table('training_plans',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='计划ID'),
    sa.Column('project_id', sa.Integer(), nullable=False, comment='项目ID'),
    sa.Column('enrollment_id', sa.Integer(), nullable=False, comment='报名ID'),
    sa.Column('user_id', sa.Integer(), nullable=False, comment='用户ID'),
    sa.Column('learner_id', sa.Integer(), nullable=True, comment='学习者画像ID'),
    sa.Column('assessment_record_id', sa.Integer(), nullable=True, comment='关联评估记录ID'),
    sa.Column('plan_content', sa.JSON(), nullable=True, comment='学习计划内容 [{stage, title, competency_ids, resources, estimated_hours, target_level, deadline}]'),
    sa.Column('total_stages', sa.Integer(), nullable=True, comment='总阶段数'),
    sa.Column('completed_stages', sa.Integer(), nullable=True, comment='已完成阶段数'),
    sa.Column('progress', sa.Float(), nullable=True, comment='进度百分比'),
    sa.Column('status', sa.String(length=20), nullable=True, comment='计划状态'),
    sa.Column('generated_by_ai', sa.Boolean(), nullable=True, comment='是否AI生成'),
    sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='创建时间'),
    sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='更新时间'),
    sa.ForeignKeyConstraint(['assessment_record_id'], ['assessment_records.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['enrollment_id'], ['training_enrollments.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['learner_id'], ['learner_profiles.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['project_id'], ['training_projects.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_training_plans_enrollment_id'), 'training_plans', ['enrollment_id'], unique=False)
    op.create_index(op.f('ix_training_plans_project_id'), 'training_plans', ['project_id'], unique=False)
    op.create_index(op.f('ix_training_plans_user_id'), 'training_plans', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_training_plans_user_id'), table_name='training_plans')
    op.drop_index(op.f('ix_training_plans_project_id'), table_name='training_plans')
    op.drop_index(op.f('ix_training_plans_enrollment_id'), table_name='training_plans')
    op.drop_table('training_plans')
    op.drop_index(op.f('ix_training_enrollments_user_id'), table_name='training_enrollments')
    op.drop_index(op.f('ix_training_enrollments_project_id'), table_name='training_enrollments')
    op.drop_index(op.f('ix_training_enrollments_learner_id'), table_name='training_enrollments')
    op.drop_table('training_enrollments')
    op.drop_index(op.f('ix_training_projects_position_id'), table_name='training_projects')
    op.drop_index(op.f('ix_training_projects_certification_id'), table_name='training_projects')
    op.drop_table('training_projects')
