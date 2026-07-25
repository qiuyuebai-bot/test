"""
认证相关 Pydantic Schema
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
import re


# ===========================================
# 登录/注册
# ===========================================

class LoginRequest(BaseModel):
    """登录请求"""
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="用户名",
        json_schema_extra={"example": "admin"},
    )
    password: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="密码",
        json_schema_extra={"example": "admin123"},
    )


class RegisterRequest(BaseModel):
    """注册请求"""
    username: str = Field(
        ...,
        min_length=3,
        max_length=50,
        description="用户名",
        json_schema_extra={"example": "new_user"},
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="密码（至少8位，包含字母和数字）",
        json_schema_extra={"example": "password123"},
    )
    email: Optional[str] = Field(
        default=None,
        max_length=100,
        description="邮箱",
        json_schema_extra={"example": "user@example.com"},
    )
    role: Optional[str] = Field(
        default="learner",
        description="角色: learner/teacher（admin角色仅由管理员创建）",
    )
    
    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        """验证用户名格式"""
        if not re.match(r'^[a-zA-Z0-9_]+$', v):
            raise ValueError("用户名只能包含字母、数字和下划线")
        return v
    
    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        """验证密码复杂度"""
        if len(v) < 8:
            raise ValueError("密码长度至少8位")
        if not re.search(r'[a-zA-Z]', v):
            raise ValueError("密码必须包含字母")
        if not re.search(r'[0-9]', v):
            raise ValueError("密码必须包含数字")
        return v
    
    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> str:
        """限制注册角色，不允许自助注册admin"""
        if v is None:
            return "learner"
        v = v.lower()
        if v == "admin":
            raise ValueError("不允许注册为admin角色，请联系系统管理员")
        if v not in ("learner", "teacher", "enterprise"):
            raise ValueError(f"无效的角色: {v}，允许: learner, teacher, enterprise")
        return v
    
    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        """验证邮箱格式"""
        if v is not None and not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
            raise ValueError("邮箱格式不正确")
        return v


class OnboardingNameRequest(BaseModel):
    """注册后设置称呼"""
    name: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description="用户在系统内显示的称呼",
        json_schema_extra={"example": "秋月白"},
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        name = v.strip()
        if not name:
            raise ValueError("请输入你的称呼")
        if len(name) > 50:
            raise ValueError("称呼不能超过50个字符")
        return name


class TokenResponse(BaseModel):
    """Token响应"""
    access_token: str = Field(..., description="访问Token")
    refresh_token: str = Field(..., description="刷新Token")
    token_type: str = Field(default="bearer", description="Token类型")


class RefreshTokenRequest(BaseModel):
    """刷新Token请求"""
    refresh_token: str = Field(..., description="刷新Token")


class UserInfoResponse(BaseModel):
    """用户信息响应"""
    user_id: int = Field(..., description="用户ID")
    username: str = Field(..., description="用户名")
    email: Optional[str] = Field(default=None, description="邮箱")
    role: str = Field(..., description="角色")
    is_active: bool = Field(..., description="是否激活")
    last_login_at: Optional[str] = Field(default=None, description="最后登录时间")
    created_at: Optional[str] = Field(default=None, description="创建时间")


class ChangePasswordRequest(BaseModel):
    """修改密码请求"""
    old_password: str = Field(
        ..., min_length=1, description="旧密码"
    )
    new_password: str = Field(
        ..., min_length=8, max_length=128, description="新密码（至少8位，包含字母和数字）"
    )
    
    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("密码长度至少8位")
        if not re.search(r'[a-zA-Z]', v):
            raise ValueError("密码必须包含字母")
        if not re.search(r'[0-9]', v):
            raise ValueError("密码必须包含数字")
        return v
