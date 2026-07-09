"""
全局异常处理器注册
按异常类型细分，统一响应格式，业务化错误文案 + 结构化日志
"""
import time
import traceback
from loguru import logger
from sqlalchemy.exc import SQLAlchemyError, IntegrityError, OperationalError

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

from app.config import settings
from app.middleware import get_request_id
from app.schemas.response import ResponseCodeEnum


def _build_error_response(
    *,
    http_status: int,
    code: int,
    message: str,
    data: object = None,
    request: Request | None = None,
    error_type: str = "",
    log_level: str = "WARNING",
) -> JSONResponse:
    """统一构造错误响应 + 结构化日志（不改变对外响应字段）"""
    if request is not None:
        method = request.method
        path = request.url.path
        rid = get_request_id()
        logger.bind(
            request_id=rid,
            method=method,
            path=path,
            error_type=error_type,
            http_status=http_status,
        ).log(log_level, f"[{error_type}] {method} {path} -> {message}")
    else:
        logger.log(log_level, f"[{error_type}] {message}")

    return JSONResponse(
        status_code=http_status,
        content={
            "code": code,
            "message": message,
            "data": data,
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    """在 app 上注册全部全局异常处理器"""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict):
            message = detail.get("message", str(detail))
        else:
            message = str(detail) if detail else "请求错误"

        return _build_error_response(
            request=request,
            http_status=exc.status_code,
            code=exc.status_code,
            message=message,
            error_type="HTTPException",
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = []
        for err in exc.errors():
            loc = " -> ".join(str(part) for part in err.get("loc", []))
            msg = err.get("msg", "")
            errors.append({"field": loc, "message": msg})

        field_hint = errors[0]["field"] if errors else ""
        friendly = "请求参数校验失败"
        if field_hint:
            friendly = f"请求参数校验失败：{field_hint} 字段有误"

        return _build_error_response(
            request=request,
            http_status=400,
            code=ResponseCodeEnum.BAD_REQUEST.value,
            message=friendly,
            data={"errors": errors} if settings.DEBUG_MODE else None,
            error_type="ValidationError",
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        error_msg = str(exc.orig) if hasattr(exc, "orig") else str(exc)

        friendly = "数据已存在或关联数据不匹配"
        lowered = error_msg.lower()
        if "unique" in lowered or "duplicate" in lowered:
            friendly = "数据已存在，请勿重复提交"
        elif "foreign key" in lowered or "fk" in lowered:
            friendly = "关联数据不存在，请检查依赖项"
        elif "not null" in lowered:
            friendly = "必填字段不能为空"

        return _build_error_response(
            request=request,
            http_status=400,
            code=ResponseCodeEnum.BAD_REQUEST.value,
            message=friendly,
            data={"detail": error_msg} if settings.DEBUG_MODE else None,
            error_type="IntegrityError",
        )

    @app.exception_handler(OperationalError)
    async def db_operational_error_handler(request: Request, exc: OperationalError):
        return _build_error_response(
            request=request,
            http_status=503,
            code=ResponseCodeEnum.SERVICE_UNAVAILABLE.value,
            message="数据库服务暂时不可用，请稍后重试",
            error_type="DBOperationalError",
            log_level="ERROR",
        )

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
        return _build_error_response(
            request=request,
            http_status=500,
            code=ResponseCodeEnum.INTERNAL_ERROR.value,
            message="数据库操作失败，请稍后重试",
            data={"detail": str(exc)} if settings.DEBUG_MODE else None,
            error_type="SQLAlchemyError",
            log_level="ERROR",
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError):
        friendly = str(exc) or "参数值不合法"
        return _build_error_response(
            request=request,
            http_status=400,
            code=ResponseCodeEnum.BAD_REQUEST.value,
            message=friendly,
            error_type="ValueError",
        )

    @app.exception_handler(FileNotFoundError)
    async def file_not_found_handler(request: Request, exc: FileNotFoundError):
        return _build_error_response(
            request=request,
            http_status=404,
            code=ResponseCodeEnum.NOT_FOUND.value,
            message="请求的资源文件不存在",
            error_type="FileNotFound",
        )

    @app.exception_handler(PermissionError)
    async def permission_error_handler(request: Request, exc: PermissionError):
        return _build_error_response(
            request=request,
            http_status=403,
            code=ResponseCodeEnum.FORBIDDEN.value,
            message="无权访问该资源",
            error_type="PermissionError",
            log_level="ERROR",
        )

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        tb_str = traceback.format_exc()
        logger.bind(
            request_id=get_request_id(),
            method=request.method,
            path=request.url.path,
            error_type=type(exc).__name__,
            http_status=500,
        ).error(
            f"[未捕获异常] {request.method} {request.url.path}\n"
            f"异常类型: {type(exc).__name__}\n"
            f"异常信息: {exc}\n"
            f"堆栈:\n{tb_str}"
        )

        friendly = "服务器内部错误，请稍后重试"
        if settings.DEBUG_MODE:
            friendly = f"服务器错误: {type(exc).__name__}: {exc}"

        return JSONResponse(
            status_code=500,
            content={
                "code": ResponseCodeEnum.INTERNAL_ERROR.value,
                "message": friendly,
                "data": {
                    "exception_type": type(exc).__name__,
                    "traceback": tb_str,
                } if settings.DEBUG_MODE else None,
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
        )
