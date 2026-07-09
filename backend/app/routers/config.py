"""
前端业务配置选项 API 路由
聚合返回前端需要的业务选项（行业/领域/培训模板/脱敏规则）
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.response import success, error, BaseResponse
from app.services.common import BaseService
from app.utils.logger import LoggerUtil
from app.utils.auth import get_current_user, CurrentUser

router = APIRouter(prefix="", tags=["业务配置"])


@router.get("/config/options", summary="获取前端业务配置选项")
def get_config_options(
    current_user: CurrentUser = Depends(get_current_user),
) -> BaseResponse:
    """
    聚合返回前端需要的业务选项（行业/领域/培训模板/脱敏规则）

    - 数据来源：backend/app/data/business_config.json
    - 前端各页面通过 configApi.getOptions() 获取，避免硬编码
    - 缓存 5 分钟，减少文件 IO
    """
    cache_key = "config_options"
    cached = BaseService.get_cache(cache_key)
    if cached is not None:
        return success(data=cached)
    try:
        from app.utils.seed_loader import load_seed_payload

        payload = load_seed_payload("business_config.json")
        data = {k: v for k, v in payload.items() if k != "_meta"}
        BaseService.set_cache(cache_key, data)
        return success(data=data)
    except Exception as e:
        LoggerUtil.log_error("获取业务配置选项失败", e)
        return error(message=f"获取业务配置选项失败: {str(e)}")
