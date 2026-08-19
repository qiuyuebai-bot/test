"""add assessment domain tables

Revision ID: b560a55bf539
Revises: 1420ed0bc6a5
Create Date: 2026-08-11 15:07:44.211329

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'b560a55bf539'
down_revision: Union[str, None] = '1420ed0bc6a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    # Preserve schemas created by the legacy create_all-before-Alembic startup.
    if all(inspector.has_table(table) for table in (
        'assessment_templates', 'assessment_records', 'competency_scores'
    )):
        return

    # 评估模板表
    op.create_table('assessment_templates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='模板ID'),
        sa.Column('position_id', sa.Integer(), nullable=False, comment='关联岗位ID'),
        sa.Column('name', sa.String(length=200), nullable=False, comment='模板名称'),
        sa.Column('description', sa.Text(), nullable=True, comment='模板描述'),
        sa.Column('competency_configs', sa.JSON(), nullable=True, comment='胜任力配置列表 [{competency_id, question_count, difficulty, assessment_method}]'),
        sa.Column('pass_threshold', sa.Float(), nullable=True, comment='通过分数线'),
        sa.Column('duration_minutes', sa.Integer(), nullable=True, comment='评估时长(分钟)'),
        sa.Column('is_active', sa.Boolean(), nullable=True, comment='是否启用'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='更新时间'),
        sa.ForeignKeyConstraint(['position_id'], ['positions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_assessment_templates_position_id'), 'assessment_templates', ['position_id'], unique=False)

    # 评估记录表
    op.create_table('assessment_records',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='记录ID'),
        sa.Column('template_id', sa.Integer(), nullable=False, comment='模板ID'),
        sa.Column('user_id', sa.Integer(), nullable=False, comment='用户ID'),
        sa.Column('learner_id', sa.Integer(), nullable=True, comment='学习者画像ID'),
        sa.Column('position_id', sa.Integer(), nullable=False, comment='岗位ID'),
        sa.Column('status', sa.String(length=20), nullable=True, comment='评估状态'),
        sa.Column('overall_score', sa.Float(), nullable=True, comment='综合得分'),
        sa.Column('overall_level', sa.Integer(), nullable=True, comment='综合能力等级(1-5)'),
        sa.Column('gap_summary', sa.JSON(), nullable=True, comment='差距摘要 [{competency_id, competency_name, current_level, required_level, gap}]'),
        sa.Column('ai_diagnosis', sa.Text(), nullable=True, comment='AI生成的诊断报告'),
        sa.Column('started_at', sa.DateTime(), nullable=True, comment='开始时间'),
        sa.Column('completed_at', sa.DateTime(), nullable=True, comment='完成时间'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='创建时间'),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='更新时间'),
        sa.ForeignKeyConstraint(['learner_id'], ['learner_profiles.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['position_id'], ['positions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['template_id'], ['assessment_templates.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_assessment_records_learner_id'), 'assessment_records', ['learner_id'], unique=False)
    op.create_index(op.f('ix_assessment_records_position_id'), 'assessment_records', ['position_id'], unique=False)
    op.create_index(op.f('ix_assessment_records_template_id'), 'assessment_records', ['template_id'], unique=False)
    op.create_index(op.f('ix_assessment_records_user_id'), 'assessment_records', ['user_id'], unique=False)

    # 胜任力评分明细表
    op.create_table('competency_scores',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False, comment='评分ID'),
        sa.Column('assessment_record_id', sa.Integer(), nullable=False, comment='评估记录ID'),
        sa.Column('competency_id', sa.Integer(), nullable=False, comment='胜任力ID'),
        sa.Column('current_level', sa.Integer(), nullable=True, comment='当前等级(1-5)'),
        sa.Column('current_score', sa.Float(), nullable=True, comment='当前得分(0-100)'),
        sa.Column('required_level', sa.Integer(), nullable=False, comment='要求等级(1-5) 快照'),
        sa.Column('gap', sa.Integer(), nullable=True, comment='差距 = required_level - current_level'),
        sa.Column('assessment_method', sa.String(length=20), nullable=True, comment='评估方式'),
        sa.Column('evidence', sa.JSON(), nullable=True, comment='评估依据(答题记录ID列表等)'),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=True, comment='创建时间'),
        sa.ForeignKeyConstraint(['assessment_record_id'], ['assessment_records.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['competency_id'], ['competencies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('assessment_record_id', 'competency_id', name='uq_record_competency')
    )
    op.create_index(op.f('ix_competency_scores_assessment_record_id'), 'competency_scores', ['assessment_record_id'], unique=False)
    op.create_index(op.f('ix_competency_scores_competency_id'), 'competency_scores', ['competency_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_competency_scores_competency_id'), table_name='competency_scores')
    op.drop_index(op.f('ix_competency_scores_assessment_record_id'), table_name='competency_scores')
    op.drop_table('competency_scores')
    op.drop_index(op.f('ix_assessment_records_user_id'), table_name='assessment_records')
    op.drop_index(op.f('ix_assessment_records_template_id'), table_name='assessment_records')
    op.drop_index(op.f('ix_assessment_records_position_id'), table_name='assessment_records')
    op.drop_index(op.f('ix_assessment_records_learner_id'), table_name='assessment_records')
    op.drop_table('assessment_records')
    op.drop_index(op.f('ix_assessment_templates_position_id'), table_name='assessment_templates')
    op.drop_table('assessment_templates')
