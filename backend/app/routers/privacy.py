"""
数据隐私与合规 API 路由
提供合规检查、脱敏规则、权限配置、密钥管理、合规文档等接口
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.response import success
from app.schemas.privacy import AnonymizationTestRequest
from app.services.privacy_service import PrivacyService
from app.utils.auth import get_current_user, CurrentUser, require_admin

router = APIRouter(prefix="/privacy", tags=["数据隐私与合规"])


@router.get("/overview", summary="获取隐私合规总览")
def get_overview(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取隐私合规总览状态"""
    return success(PrivacyService.get_overview())


@router.get("/compliance", summary="获取隐私合规检查项")
def get_compliance(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取隐私合规检查项列表"""
    return success(PrivacyService.get_compliance_items())


@router.get("/anonymization", summary="获取数据脱敏规则")
def get_anonymization(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取数据脱敏规则列表"""
    return success(PrivacyService.get_anonymization_rules())


@router.post("/anonymization/test", summary="测试数据脱敏")
def test_anonymization(
    req: AnonymizationTestRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
):
    """根据字段类型对输入值进行脱敏测试（仅管理员）"""
    result = PrivacyService.test_anonymization(req.field, req.value)
    return success(result)


@router.get("/permissions", summary="获取数据权限配置")
def get_permissions(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取数据权限配置列表（基于系统角色模型）"""
    return success(PrivacyService.get_permission_config())


@router.get("/keys", summary="获取密钥管理信息（脱敏展示）")
def get_keys(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(require_admin),
):
    """获取密钥管理信息，仅返回掩码后的密钥值（仅管理员）"""
    return success(PrivacyService.get_key_info())


@router.get("/documents", summary="获取合规文档列表")
def get_documents(
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    """获取合规文档列表"""
    return success(PrivacyService.get_compliance_documents())
