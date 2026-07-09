"""add composite indexes

Revision ID: a3f7c2e8b4d1
Revises: 8455fe7f1990
Create Date: 2026-07-08 09:00:00.000000

添加 4 项复合索引，优化高频查询路径：
- learning_resources(learner_id, created_at DESC) — 学习者资源分页
- answer_records(learner_id, created_at DESC) — 学习者答题历史
- knowledge_docs(status, updated_at) — 文档状态筛选
- agent_tasks(status, created_at) — 任务状态查询
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a3f7c2e8b4d1'
down_revision: Union[str, None] = '8455fe7f1990'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        'ix_learning_resources_learner_id_created_at',
        'learning_resources',
        ['learner_id', sa.text('created_at DESC')],
    )
    op.create_index(
        'ix_answer_records_learner_id_created_at',
        'answer_records',
        ['learner_id', sa.text('created_at DESC')],
    )
    op.create_index(
        'ix_knowledge_docs_status_updated_at',
        'knowledge_docs',
        ['status', 'updated_at'],
    )
    op.create_index(
        'ix_agent_tasks_status_created_at',
        'agent_tasks',
        ['status', 'created_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_agent_tasks_status_created_at', table_name='agent_tasks')
    op.drop_index('ix_knowledge_docs_status_updated_at', table_name='knowledge_docs')
    op.drop_index('ix_answer_records_learner_id_created_at', table_name='answer_records')
    op.drop_index('ix_learning_resources_learner_id_created_at', table_name='learning_resources')
