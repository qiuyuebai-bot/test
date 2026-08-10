"""Dashboard 用户体验状态模型。"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class DashboardGuidanceState(Base):
    """保存跨设备可用的 Dashboard 引导状态。"""

    __tablename__ = "dashboard_guidance_states"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_dashboard_guidance_state_user"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    onboarding_completed_at = Column(DateTime, nullable=True)
    dashboard_guidance_dismissed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
