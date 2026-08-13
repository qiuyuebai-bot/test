"""
认证发证域 Pydantic Schemas
"""
from typing import Optional, List, Any, Dict
from datetime import datetime
from pydantic import BaseModel, Field


# ===========================================
# 认证定义 Schemas
# ===========================================

class CertificationCreate(BaseModel):
    """创建认证"""
    position_id: int = Field(..., description="关联岗位ID")
    name: str = Field(..., max_length=200, description="认证名称")
    code: str = Field(..., max_length=50, description="认证编码（唯一）")
    level: Optional[str] = Field(None, description="认证级别 junior/mid/senior")
    description: Optional[str] = None
    validity_period_months: int = Field(0, ge=0, description="有效期(月)，0表示永久")
    issuer: Optional[str] = Field(None, max_length=100, description="发证机构")


class CertificationUpdate(BaseModel):
    """更新认证"""
    name: Optional[str] = Field(None, max_length=200)
    level: Optional[str] = None
    description: Optional[str] = None
    validity_period_months: Optional[int] = Field(None, ge=0)
    issuer: Optional[str] = Field(None, max_length=100)
    is_active: Optional[bool] = None


# ===========================================
# 发证规则 Schemas
# ===========================================

class CertificationRuleCreate(BaseModel):
    """创建发证规则"""
    certification_id: int = Field(..., description="认证ID")
    rule_type: str = Field(..., description="规则类型: overall_score/competency_level/all_mandatory_met")
    rule_config: Dict[str, Any] = Field(default_factory=dict, description="规则配置")


# ===========================================
# 认证记录 Schemas
# ===========================================

class CertificationApplyRequest(BaseModel):
    """申请认证请求"""
    certification_id: int = Field(..., description="认证ID")
    assessment_record_id: int = Field(..., description="评估记录ID")
    learner_id: int = Field(..., description="学习者画像ID")


class CertificationReviewRequest(BaseModel):
    """审核认证请求"""
    comment: Optional[str] = Field(None, description="审核意见")
