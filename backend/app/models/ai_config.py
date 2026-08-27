"""Per-user AI provider configuration persisted by the backend.

Secret values are stored in encrypted columns by ``AIConfigService``.  The ORM
model intentionally has no plaintext API-key property so accidental response
serialization cannot disclose credentials.
"""

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class UserAIConfig(Base):
    """The one active provider/model configuration owned by one user."""

    __tablename__ = "user_ai_configs"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_ai_configs_user_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True, comment="AI配置ID")
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True, comment="所属用户ID")
    provider = Column(String(64), nullable=False, default="custom", comment="提供商标识")
    protocol = Column(String(64), nullable=False, default="openai_chat", comment="协议标识")
    base_url = Column(String(500), nullable=False, default="", comment="API基础地址")
    api_key_encrypted = Column(Text, nullable=True, comment="加密后的API密钥")
    selected_model = Column(String(255), nullable=True, comment="当前选择的模型")
    available_models = Column(JSON, nullable=False, default=list, comment="最近探测到的模型列表")
    proxy_url = Column(String(500), nullable=True, default="", comment="反向代理地址")
    proxy_password_encrypted = Column(Text, nullable=True, comment="加密后的代理密码")
    extra_config = Column(JSON, nullable=False, default=dict, comment="协议专用非敏感配置")
    last_test_status = Column(String(32), nullable=False, default="never", comment="最近连接测试状态")
    last_test_message = Column(String(500), nullable=True, comment="最近连接测试脱敏消息")
    last_tested_at = Column(DateTime, nullable=True, comment="最近连接测试时间")
    is_active = Column(Boolean, nullable=False, default=True, comment="是否为当前生效配置")
    created_at = Column(DateTime, server_default=func.now(), nullable=False, comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False, comment="更新时间")

    user = relationship("User", back_populates="ai_config")

    def __repr__(self) -> str:
        return f"<UserAIConfig(user_id={self.user_id}, provider={self.provider}, model={self.selected_model})>"
