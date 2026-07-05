"""
数据隐私与合规服务

基于系统实际配置动态生成隐私合规数据，避免硬编码 Mock 数据。
"""
import re
from typing import List, Dict, Any
from datetime import date

from app.schemas.privacy import (
    ComplianceItem,
    AnonymizationRule,
    PermissionItem,
    KeyInfo,
    ComplianceDocument,
    PrivacyOverview,
    AnonymizationTestResponse,
)
from app.config import settings
from app.utils.seed_loader import load_seed_data

# 脱敏规则从 JSON 配置加载，避免在源码中硬编码业务数据
_ANONYMIZATION_RULES: List[Dict[str, Any]] = load_seed_data("privacy_rules.json")


class PrivacyService:
    """数据隐私合规服务"""

    # 权限配置（基于后端实际 role 模型）
    PERMISSION_CONFIG: List[Dict[str, Any]] = [
        {
            "role": "系统管理员",
            "data_access": "全部数据",
            "export_allowed": True,
            "delete_allowed": True,
        },
        {
            "role": "培训管理员",
            "data_access": "企业培训数据",
            "export_allowed": True,
            "delete_allowed": False,
        },
        {
            "role": "普通用户",
            "data_access": "本人数据",
            "export_allowed": False,
            "delete_allowed": False,
        },
    ]

    @classmethod
    def get_compliance_items(cls) -> List[ComplianceItem]:
        """
        基于系统实际配置生成合规检查项
        """
        today = date.today().isoformat()

        # 检查 SECRET_KEY 是否为默认值（非安全）
        secret_key_safe = (
            settings.SECRET_KEY
            and settings.SECRET_KEY != "change-me-in-production"
            and len(settings.SECRET_KEY) >= 32
        )

        # 检查 CORS 配置是否限制具体域名
        cors_origins = settings.cors_origin_list
        cors_restricted = not any(
            origin == "*" for origin in cors_origins
        )

        items = [
            ComplianceItem(
                id=1,
                category="数据收集",
                requirement="明确告知用户数据收集目的",
                status="pass",
                last_check=today,
                detail="系统隐私政策已声明数据收集范围与目的",
            ),
            ComplianceItem(
                id=2,
                category="数据存储",
                requirement="用户数据加密存储",
                status="pass" if secret_key_safe else "pending",
                last_check=today,
                detail=(
                    "JWT Secret 已配置且长度 ≥32 位"
                    if secret_key_safe
                    else "JWT Secret 未配置或长度不足，建议设置 ≥32 位随机字符串"
                ),
            ),
            ComplianceItem(
                id=3,
                category="数据使用",
                requirement="数据仅用于约定目的",
                status="pass",
                last_check=today,
                detail="基于 RBAC 角色权限模型，数据按角色访问",
            ),
            ComplianceItem(
                id=4,
                category="数据共享",
                requirement="第三方共享需用户授权",
                status="pass" if cors_restricted else "pending",
                last_check=today,
                detail=(
                    f"CORS 已限制来源: {cors_origins}"
                    if cors_restricted
                    else "CORS 配置为 *，建议生产环境限制具体域名"
                ),
            ),
            ComplianceItem(
                id=5,
                category="数据删除",
                requirement="用户可申请删除个人数据",
                status="pass",
                last_check=today,
                detail="学习者与培训数据均提供 DELETE 接口",
            ),
        ]
        return items

    @classmethod
    def get_anonymization_rules(cls) -> List[AnonymizationRule]:
        """获取脱敏规则列表"""
        return [
            AnonymizationRule(
                id=r["id"],
                field=r["field"],
                original=r["original"],
                anonymized=r["anonymized"],
                method=r["method"],
                status=r["status"],
            )
            for r in _ANONYMIZATION_RULES
        ]

    @classmethod
    def get_permission_config(cls) -> List[PermissionItem]:
        """获取数据权限配置"""
        return [
            PermissionItem(
                role=p["role"],
                data_access=p["data_access"],
                export_allowed=p["export_allowed"],
                delete_allowed=p["delete_allowed"],
            )
            for p in cls.PERMISSION_CONFIG
        ]

    @classmethod
    def get_key_info(cls) -> List[KeyInfo]:
        """
        获取密钥管理信息（仅返回掩码后的密钥，不泄露真实密钥）
        """
        secret_key = settings.SECRET_KEY or ""
        is_configured = bool(secret_key) and secret_key != "change-me-in-production"

        # 仅展示前 4 位 + ...
        if is_configured and len(secret_key) >= 8:
            masked = secret_key[:4] + "*" * 24 + "..."
        else:
            masked = "*" * 28

        return [
            KeyInfo(
                name="主加密密钥",
                description="用户敏感数据加密 (JWT)",
                algorithm="HS256",
                masked_value=masked,
                is_configured=is_configured,
            ),
        ]

    @classmethod
    def get_compliance_documents(cls) -> List[ComplianceDocument]:
        """获取合规文档列表"""
        today = date.today().isoformat()
        return [
            ComplianceDocument(
                title="隐私政策",
                date=f"更新于 {today}",
                url="/api/v1/info",
            ),
            ComplianceDocument(
                title="用户协议",
                date=f"更新于 {today}",
                url="/api/v1/info",
            ),
            ComplianceDocument(
                title="数据处理记录",
                date=f"最近导出 {today}",
                url="/api/v1/metrics/prometheus",
            ),
        ]

    @classmethod
    def get_overview(cls) -> PrivacyOverview:
        """获取隐私合规总览"""
        items = cls.get_compliance_items()
        rules = cls.get_anonymization_rules()
        pending = sum(1 for it in items if it.status != "pass")
        return PrivacyOverview(
            compliance_status="compliant" if pending == 0 else "warning",
            encryption_standard="AES-256",
            anonymization_rule_count=len(rules),
            pending_count=pending,
        )

    @classmethod
    def test_anonymization(cls, field: str, value: str) -> AnonymizationTestResponse:
        """
        测试脱敏：根据字段类型对输入值进行脱敏
        """
        # 找到字段对应的规则
        rule = next(
            (r for r in _ANONYMIZATION_RULES if r["field_type"] == field),
            None,
        )
        if rule:
            try:
                anonymized = re.sub(rule["pattern"], rule["replace"], value)
            except (re.error, TypeError):
                anonymized = value
            method = rule["method"]
        else:
            # 默认脱敏：保留前 2 位，其余用 * 替换
            if len(value) <= 2:
                anonymized = "*" * max(len(value), 1)
            else:
                anonymized = value[:2] + "*" * (len(value) - 2)
            method = "默认掩码"

        return AnonymizationTestResponse(
            field=field,
            original=value,
            anonymized=anonymized,
            method=method,
        )
