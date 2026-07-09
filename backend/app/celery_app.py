"""
Celery 异步任务配置
处理大批量多用户Agent协同任务，支持后台长时间运行
"""
from celery import Celery
from loguru import logger
from typing import Optional

from app.config import settings

# 创建 Celery 实例
celery_app = Celery(
    "agent_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

# 配置
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Shanghai",
    enable_utc=False,
    task_track_started=True,
    task_time_limit=3600,  # 1小时超时
    task_soft_time_limit=3300,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    task_acks_late=True,
    result_expires=86400,
)

# 自动发现任务
celery_app.autodiscover_tasks(["app.celery_tasks"])


@celery_app.task(
    bind=True,
    name="agent_tasks.full_pipeline",
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def full_pipeline_task(
    self,
    task_id: int,
    learner_id: int,
    target_topic: str,
    resource_type: str = "guide",
    industry: Optional[str] = None,
):
    """
    完整流水线异步任务（Celery版本）
    
    Args:
        self: Celery任务实例
        task_id: 任务ID
        learner_id: 学习者ID
        target_topic: 目标主题
        resource_type: 资源类型
        industry: 行业
    """
    from app.agents.orchestrator import orchestrator
    
    logger.info(f"[Celery] 开始完整流水线任务: task_id={task_id}")
    
    try:
        # 更新状态
        self.update_state(state="RUNNING", meta={"stage": "init", "progress": 0})
        
        result = orchestrator.run_full_pipeline(
            task_id=task_id,
            learner_id=learner_id,
            target_topic=target_topic,
            resource_type=resource_type,
            industry=industry,
        )
        
        logger.info(f"[Celery] 任务完成: task_id={task_id}")
        
        return {
            "status": "success",
            "task_id": task_id,
            "result": str(result),
        }
        
    except Exception as e:
        logger.error(f"[Celery] 任务失败: task_id={task_id}, error={e}")
        self.update_state(state="FAILURE", meta={"error": str(e)})
        raise


@celery_app.task(
    name="agent_tasks.batch_generation",
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def batch_generation_task(
    learner_ids: list,
    target_topic: str,
    resource_type: str = "guide",
    industry: Optional[str] = None,
):
    """
    批量生成任务（多用户）
    
    Args:
        learner_ids: 学习者ID列表
        target_topic: 目标主题
        resource_type: 资源类型
        industry: 行业
    """
    from app.agents.orchestrator import orchestrator
    from app.database import get_db_context
    from app.models import AgentTask
    
    logger.info(f"[Celery] 开始批量生成任务: {len(learner_ids)}个学习者")
    
    results = []
    total = len(learner_ids)
    
    for idx, learner_id in enumerate(learner_ids):
        try:
            # 创建任务
            with get_db_context() as db:
                task = AgentTask(
                    learner_id=learner_id,
                    task_name=f"批量生成 - {target_topic}",
                    task_type="resource_generation",
                    agent_type="system",
                    flow_stage="init",
                    status="pending",
                    progress=0,
                )
                db.add(task)
                db.flush()
                task_id = task.id
                db.commit()
            
            # 执行流水线
            orchestrator.run_full_pipeline(
                task_id=task_id,
                learner_id=learner_id,
                target_topic=target_topic,
                resource_type=resource_type,
                industry=industry,
            )
            
            results.append({
                "learner_id": learner_id,
                "task_id": task_id,
                "status": "success",
                "progress": (idx + 1) / total * 100,
            })
            
        except Exception as e:
            results.append({
                "learner_id": learner_id,
                "status": "failed",
                "error": str(e),
            })
    
    return {
        "total": total,
        "success": sum(1 for r in results if r["status"] == "success"),
        "failed": sum(1 for r in results if r["status"] == "failed"),
        "results": results,
    }


@celery_app.task(
    bind=True,
    name="agent_tasks.generate_resources",
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def generate_resources_task(
    self,
    learner_id: int,
    target_topic: str,
    industry: Optional[str] = None,
):
    """
    异步生成三类个性化学习资源（Celery 版本）
    
    供 API 接口调用，替换 BackgroundTasks
    
    Args:
        self: Celery任务实例（bind=True）
        learner_id: 学习者ID
        target_topic: 目标主题
        industry: 行业
    """
    from app.domains.resource.service import ResourceGenerationService
    
    logger.info(f"[Celery] 开始资源生成: learner_id={learner_id}, topic={target_topic}")
    
    try:
        # 阶段1: 学情诊断
        self.update_state(
            state="PROGRESS",
            meta={"stage": "diagnosis", "progress": 10, "message": "正在进行学情诊断..."}
        )
        
        # 阶段2: 知识检索
        self.update_state(
            state="PROGRESS",
            meta={"stage": "retrieval", "progress": 25, "message": "正在检索知识库..."}
        )
        
        # 阶段3: 资源生成
        self.update_state(
            state="PROGRESS",
            meta={"stage": "generation", "progress": 40, "message": "正在生成三类资源..."}
        )
        
        result = ResourceGenerationService.generate_all_resources(
            learner_id=learner_id,
            target_topic=target_topic,
            industry=industry,
        )
        
        if result.get("success"):
            self.update_state(
                state="PROGRESS",
                meta={
                    "stage": "completed",
                    "progress": 100,
                    "message": "资源生成完成",
                    "resource_count": result.get("resource_count", 0),
                    "avg_match_score": result.get("avg_match_score", 0),
                }
            )
            
            logger.info(f"[Celery] 资源生成完成: learner_id={learner_id}")
            
            return {
                "status": "success",
                "learner_id": learner_id,
                "target_topic": target_topic,
                "resource_count": result.get("resource_count", 0),
                "avg_match_score": result.get("avg_match_score", 0),
                "result": result,
            }
        else:
            raise Exception(result.get("error", "资源生成失败"))
        
    except Exception as e:
        logger.error(f"[Celery] 资源生成失败: learner_id={learner_id}, error={e}")
        self.update_state(
            state="FAILURE",
            meta={"stage": "failed", "progress": 0, "error": str(e)}
        )
        raise


@celery_app.task(
    bind=True,
    name="agent_tasks.batch_generate_resources",
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
)
def batch_generate_resources_task(
    self,
    learner_ids: list,
    target_topic: str,
    industry: Optional[str] = None,
):
    """
    批量异步生成资源（多学习者）
    
    支持进度追踪，每个学习者完成后更新进度
    
    Args:
        self: Celery任务实例
        learner_ids: 学习者ID列表
        target_topic: 目标主题
        industry: 行业
    """
    from app.domains.resource.service import ResourceGenerationService
    
    total = len(learner_ids)
    results = []
    
    logger.info(f"[Celery] 批量资源生成: {total}个学习者")
    
    for idx, learner_id in enumerate(learner_ids):
        try:
            self.update_state(
                state="PROGRESS",
                meta={
                    "stage": "batch_generation",
                    "progress": int((idx / total) * 100),
                    "current": idx + 1,
                    "total": total,
                    "message": f"正在为学习者 {learner_id} 生成资源 ({idx + 1}/{total})..."
                }
            )
            
            result = ResourceGenerationService.generate_all_resources(
                learner_id=learner_id,
                target_topic=target_topic,
                industry=industry,
            )
            
            results.append({
                "learner_id": learner_id,
                "status": "success" if result.get("success") else "failed",
                "resource_count": result.get("resource_count", 0),
                "avg_match_score": result.get("avg_match_score", 0),
                "error": result.get("error"),
            })
            
        except Exception as e:
            logger.error(f"[Celery] 批量生成-学习者失败: learner_id={learner_id}, error={e}")
            results.append({
                "learner_id": learner_id,
                "status": "failed",
                "error": str(e),
            })
    
    self.update_state(
        state="PROGRESS",
        meta={
            "stage": "batch_completed",
            "progress": 100,
            "message": f"批量生成完成: {total}个学习者"
        }
    )
    
    return {
        "status": "success",
        "total": total,
        "success_count": sum(1 for r in results if r["status"] == "success"),
        "failed_count": sum(1 for r in results if r["status"] == "failed"),
        "results": results,
    }
