"""
数据隐私与合规相关 Schema
"""
from pydantic import BaseModel, Field
from typing import Optional


class ComplianceItem(BaseModel):
    """合规检查项"""
    id: int = Field(..., description="检查项ID")
    category: str = Field(..., description="分类")
    requirement: str = Field(..., description="要求描述")
    status: str = Field(..., description="状态(pass/pending/fail)")
    last_check: str = Field(..., description="最近检查时间")
    detail: Optional[str] = Field(None, description="检查详情")


class AnonymizationRule(BaseModel):
    """脱敏规则"""
    id: int = Field(..., description="规则ID")
    field: str = Field(..., description="字段名称")
    original: str = Field(..., description="原始示例数据")
    anonymized: str = Field(..., description="脱敏后示例数据")
    method: str = Field(..., description="脱敏方法")
    status: str = Field(..., description="状态(active/draft)")


class PermissionItem(BaseModel):
    """数据权限配置项"""
    role: str = Field(..., description="角色")
    data_access: str = Field(..., description="数据访问范围")
    export_allowed: bool = Field(..., description="是否允许导出")
    delete_allowed: bool = Field(..., description="是否允许删除")


class KeyInfo(BaseModel):
    """密钥管理信息（脱敏展示）"""
    name: str = Field(..., description="密钥名称")
    description: str = Field(..., description="用途说明")
    algorithm: str = Field(..., description="加密算法")
    masked_value: str = Field(..., description="掩码后的密钥（仅展示）")
    is_configured: bool = Field(..., description="是否已配置")


class ComplianceDocument(BaseModel):
    """合规文档"""
    title: str = Field(..., description="文档标题")
    date: str = Field(..., description="更新/导出时间")
    url: str = Field(..., description="文档链接")


class PrivacyOverview(BaseModel):
    """隐私合规总览"""
    compliance_status: str = Field(..., description="合规状态(compliant/warning)")
    encryption_standard: str = Field(..., description="加密标准")
    anonymization_rule_count: int = Field(..., description="脱敏规则数")
    pending_count: int = Field(..., description="待处理项数")


class AnonymizationTestRequest(BaseModel):
    """脱敏测试请求"""
    field: str = Field(..., description="字段类型(name/phone/idcard/email/address)")
    value: str = Field(..., description="待脱敏的原始值")


class AnonymizationTestResponse(BaseModel):
    """脱敏测试响应"""
    field: str = Field(..., description="字段类型")
    original: str = Field(..., description="原始值")
    anonymized: str = Field(..., description="脱敏结果")
    method: str = Field(..., description="使用的脱敏方法")
