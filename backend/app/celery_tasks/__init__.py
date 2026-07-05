"""
Celery 异步任务
"""
from app.celery_app import (
    celery_app,
    full_pipeline_task,
    batch_generation_task,
    generate_resources_task,
    batch_generate_resources_task,
)

__all__ = [
    "celery_app",
    "full_pipeline_task",
    "batch_generation_task",
    "generate_resources_task",
    "batch_generate_resources_task",
]
