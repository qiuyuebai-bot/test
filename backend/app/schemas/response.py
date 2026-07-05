"""
统一返回结果封装
标准化接口返回体，包含状态码、消息、业务数据、时间戳
错误响应使用JSONResponse返回正确的HTTP状态码
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Any, Generic, TypeVar
from datetime import datetime
from app.utils.datetime import utcnow_naive
from enum import Enum
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder


class ResponseCodeEnum(Enum):
    """响应状态码枚举"""
    SUCCESS = 200          # 成功
    CREATED = 201          # 创建成功
    BAD_REQUEST = 400      # 请求参数错误
    UNAUTHORIZED = 401     # 未授权
    FORBIDDEN = 403        # 禁止访问
    NOT_FOUND = 404        # 资源不存在
    INTERNAL_ERROR = 500   # 内部服务器错误
    SERVICE_UNAVAILABLE = 503  # 服务不可用


T = TypeVar("T")


class BaseResponse(BaseModel, Generic[T]):
    """统一返回结果基类"""
    
    code: int = Field(
        default=ResponseCodeEnum.SUCCESS.value,
        description="状态码"
    )
    message: str = Field(
        default="操作成功",
        description="提示消息"
    )
    data: Optional[T] = Field(
        default=None,
        description="业务数据"
    )
    timestamp: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        description="响应时间戳"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "code": 200,
                "message": "操作成功",
                "data": None,
                "timestamp": "2024-03-15 14:30:00"
            }
        }
    )


class PagedData(BaseModel, Generic[T]):
    """分页数据结构"""
    
    items: list[T] = Field(default_factory=list, description="数据列表")
    total: int = Field(default=0, description="总数量")
    page: int = Field(default=1, description="当前页码")
    page_size: int = Field(default=10, description="每页数量")
    total_pages: int = Field(default=0, description="总页数")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "items": [],
                "total": 100,
                "page": 1,
                "page_size": 10,
                "total_pages": 10
            }
        }
    )


class PagedResponse(BaseResponse[PagedData[T]]):
    """分页返回结果"""
    pass


# ===========================================
# 快捷响应构造函数
# ===========================================

def _make_response(code: int, message: str, data: Any = None, http_status: int = None) -> JSONResponse:
    """构造统一JSON响应"""
    http_status = http_status or code
    return JSONResponse(
        status_code=http_status,
        content={
            "code": code,
            "message": message,
            "data": jsonable_encoder(data),
            "timestamp": utcnow_naive().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


def success(data: Any = None, message: str = "操作成功") -> JSONResponse:
    """成功响应"""
    return _make_response(
        code=ResponseCodeEnum.SUCCESS.value,
        message=message,
        data=data,
        http_status=200,
    )


def created(data: Any = None, message: str = "创建成功") -> JSONResponse:
    """创建成功响应"""
    return _make_response(
        code=ResponseCodeEnum.CREATED.value,
        message=message,
        data=data,
        http_status=201,
    )


def error(
    code: int = ResponseCodeEnum.INTERNAL_ERROR.value,
    message: str = "操作失败",
    data: Any = None
) -> JSONResponse:
    """错误响应"""
    return _make_response(code=code, message=message, data=data)


def bad_request(message: str = "请求参数错误", data: Any = None) -> JSONResponse:
    """参数错误响应"""
    return _make_response(
        code=ResponseCodeEnum.BAD_REQUEST.value,
        message=message,
        data=data,
    )


def unauthorized(message: str = "未授权访问") -> JSONResponse:
    """未授权响应"""
    return _make_response(
        code=ResponseCodeEnum.UNAUTHORIZED.value,
        message=message,
        data=None,
    )


def forbidden(message: str = "禁止访问") -> JSONResponse:
    """禁止访问响应"""
    return _make_response(
        code=ResponseCodeEnum.FORBIDDEN.value,
        message=message,
        data=None,
    )


def not_found(message: str = "资源不存在") -> JSONResponse:
    """资源不存在响应"""
    return _make_response(
        code=ResponseCodeEnum.NOT_FOUND.value,
        message=message,
        data=None,
    )


def paged_success(
    items: list,
    total: int,
    page: int = 1,
    page_size: int = 10,
    message: str = "查询成功"
) -> JSONResponse:
    """分页成功响应"""
    total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
    return JSONResponse(
        status_code=200,
        content={
            "code": ResponseCodeEnum.SUCCESS.value,
            "message": message,
            "data": {
                "items": jsonable_encoder(items),
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": total_pages,
            },
            "timestamp": utcnow_naive().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )