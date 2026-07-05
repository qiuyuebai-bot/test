"""
脱敏数据存储记录表 ORM 模型
存储数据脱敏处理记录
"""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.sql import func
from app.database import Base
import enum


class AnonymizeMethodEnum(enum.Enum):
    """脱敏方法枚举"""
    PARTIAL_MASK = "partial_mask"      # 部分掩码
    FULL_MASK = "full_mask"            # 完全掩码
    HASH_REPLACE = "hash_replace"      # 哈希替换
    RANDOM_REPLACE = "random_replace"  # 随机替换
    TRUNCATE = "truncate"              # 截断


class DataTypeEnum(enum.Enum):
    """数据类型枚举"""
    NAME = "name"          # 姓名
    PHONE = "phone"        # 手机号
    ID_CARD = "id_card"    # 身份证号
    EMAIL = "email"        # 邮箱
    ADDRESS = "address"    # 地址
    COMPANY = "company"    # 企业名称
    OTHER = "other"        # 其他


class AnonymizedData(Base):
    """脱敏数据存储记录表"""
    
    __tablename__ = "anonymized_data"
    
    # 主键
    id = Column(Integer, primary_key=True, autoincrement=True, comment="记录ID")
    
    # 数据类型
    data_type = Column(String(20), nullable=False, index=True, comment="数据类型")
    field_name = Column(String(50), nullable=False, comment="字段名称")
    
    # 关联用户（可选）
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, comment="关联用户ID")
    
    # 原始数据（加密存储）
    original_data_hash = Column(String(64), nullable=True, comment="原始数据哈希(MD5)")
    original_data_encrypted = Column(Text, nullable=True, comment="原始数据(加密)")
    
    # 脱敏结果
    anonymized_data = Column(String(200), nullable=False, comment="脱敏后数据")
    anonymize_method = Column(String(20), nullable=False, comment="脱敏方法")
    
    # 脱敏规则配置
    mask_pattern = Column(String(50), nullable=True, comment="掩码模式")
    preserve_prefix = Column(Integer, default=0, comment="保留前缀长度")
    preserve_suffix = Column(Integer, default=0, comment="保留后缀长度")
    mask_char = Column(String(1), default="*", comment="掩码字符")
    
    # 脱敏示例
    original_example = Column(String(100), nullable=True, comment="原始数据示例")
    anonymized_example = Column(String(100), nullable=True, comment="脱敏后示例")
    
    # 脱敏状态
    is_active = Column(Boolean, default=True, comment="规则是否激活")
    applied_count = Column(Integer, default=0, comment="应用次数")
    
    # 合规信息
    compliance_type = Column(String(50), default="GDPR", comment="合规类型")
    compliance_notes = Column(Text, nullable=True, comment="合规说明")
    
    # 来源信息
    source_table = Column(String(50), nullable=True, comment="来源表名")
    source_record_id = Column(Integer, nullable=True, comment="来源记录ID")
    
    # 时间字段
    created_at = Column(DateTime, server_default=func.now(), comment="创建时间")
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), comment="更新时间")
    last_applied_at = Column(DateTime, nullable=True, comment="最后应用时间")
    
    def __repr__(self) -> str:
        return f"<AnonymizedData(id={self.id}, type={self.data_type}, method={self.anonymize_method})>"