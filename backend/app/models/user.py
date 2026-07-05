"""
用户表 ORM 模型
存储系统用户基本信息
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum


class UserRoleEnum(enum.Enum):
    """用户角色枚举"""
    ADMIN = "admin"           # 系统管理员
    TEACHER = "teacher"       # 教师/培训管理员
    LEARNER = "learner"       # 学习者
    ENTERPRISE = "enterprise" # 企业管理员


class User(Base):
    """用户表"""
    
    __tablename__ = "users"
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="用户ID")
    
    # 基本信息
    username = Column(String(50), unique=True, nullable=False, index=True, comment="用户名")
    password_hash = Column(String(255), nullable=False, comment="密码哈希")
    email = Column(String(100), unique=True, nullable=True, comment="邮箱")
    phone = Column(String(20), nullable=True, comment="手机号")
    
    # 角色与权限
    role = Column(
        SQLEnum(UserRoleEnum),
        default=UserRoleEnum.LEARNER,
        nullable=False,
        comment="用户角色"
    )
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_verified = Column(Boolean, default=False, comment="是否已验证")
    
    # 企业关联（企业用户）
    enterprise_name = Column(String(100), nullable=True, comment="所属企业")
    
    # 时间字段
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    last_login_at = Column(DateTime, nullable=True, comment="最后登录时间")
    
    # 关联关系
    learner_profile = relationship("LearnerProfile", back_populates="user", uselist=False)
    answer_records = relationship("AnswerRecord", back_populates="user")
    learning_paths = relationship("LearningPath", back_populates="user")
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username}, role={self.role.value})>"