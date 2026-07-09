"""
公共依赖注入模块
集中管理路由层常用的依赖函数，避免重复代码
"""
from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import LearnerProfile


def get_learner_or_404(learner_id: int, db: Session = Depends(get_db)) -> LearnerProfile:
    """公共依赖：根据 ID 获取学习者，不存在则返回 404

    Args:
        learner_id: 学习者ID
        db: 数据库会话（自动注入）

    Returns:
        LearnerProfile 实例

    Raises:
        HTTPException: 404 学习者不存在
    """
    learner = db.query(LearnerProfile).filter(LearnerProfile.id == learner_id).first()
    if not learner:
        raise HTTPException(status_code=404, detail="学习者不存在")
    return learner
