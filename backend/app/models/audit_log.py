"""
审计日志 ORM 模型
记录关键操作（登录、数据变更、导出等），支持追溯与合规审计
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from sqlalchemy.sql import func
from app.database import Base


class AuditLog(Base):
    """审计日志表"""

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True, comment="日志ID")

    created_at = Column(
        DateTime,
        server_default=func.now(),
        nullable=False,
        index=True,
        comment="记录时间",
    )

    user_id = Column(Integer, nullable=True, index=True, comment="操作用户ID")

    username = Column(String(50), nullable=True, comment="操作用户名")

    action = Column(
        String(32),
        nullable=False,
        index=True,
        comment="操作类型: LOGIN/LOGOUT/REGISTER/CREATE/UPDATE/DELETE/EXPORT/SEARCH",
    )

    resource_type = Column(
        String(32),
        nullable=True,
        index=True,
        comment="资源类型: auth/learner/knowledge/agent/training/resource/report",
    )

    resource_id = Column(String(64), nullable=True, comment="资源ID")

    method = Column(String(10), nullable=False, comment="HTTP方法: GET/POST/PUT/DELETE/PATCH")

    path = Column(String(255), nullable=False, comment="请求路径")

    status_code = Column(Integer, nullable=True, comment="HTTP响应状态码")

    ip_address = Column(String(45), nullable=True, comment="客户端IP地址")

    user_agent = Column(String(255), nullable=True, comment="User-Agent")

    duration_ms = Column(Integer, nullable=True, comment="请求耗时(毫秒)")

    request_id = Column(String(64), nullable=True, comment="请求追踪ID")

    details = Column(Text, nullable=True, comment="附加信息(JSON格式)")

    __table_args__ = (
        Index("ix_audit_logs_user_action", "user_id", "action"),
        Index("ix_audit_logs_resource", "resource_type", "resource_id"),
    )

    def __repr__(self):
        return f"<AuditLog(id={self.id}, action={self.action}, user={self.username}, path={self.path})>"
