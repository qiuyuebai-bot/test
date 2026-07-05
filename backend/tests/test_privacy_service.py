"""
数据隐私服务单元测试
测试范围：脱敏规则、合规检查项、权限配置、总览统计、脱敏测试逻辑
"""
import pytest

from app.services.privacy_service import PrivacyService


class TestAnonymizationRules:
    """脱敏规则配置测试"""

    def test_rules_have_required_fields(self):
        rules = PrivacyService.get_anonymization_rules()
        assert len(rules) == 5
        for r in rules:
            assert r.id
            assert r.field
            assert r.original
            assert r.anonymized
            assert r.method
            assert r.status in ("active", "draft")

    def test_rule_ids_unique(self):
        rules = PrivacyService.get_anonymization_rules()
        ids = [r.id for r in rules]
        assert len(ids) == len(set(ids))


class TestTestAnonymization:
    """test_anonymization 是纯逻辑函数，是重构安全网的核心"""

    def test_phone_anonymization(self):
        resp = PrivacyService.test_anonymization("phone", "13812345678")
        assert resp.field == "phone"
        assert resp.original == "13812345678"
        assert resp.anonymized == "138****5678"
        assert resp.method == "中间掩码"

    def test_name_anonymization(self):
        resp = PrivacyService.test_anonymization("name", "张明远")
        assert resp.anonymized == "张*"
        assert resp.method == "部分掩码"

    def test_idcard_anonymization(self):
        resp = PrivacyService.test_anonymization("idcard", "310101199001011234")
        assert resp.anonymized == "310101********1234"
        assert resp.method == "首尾保留"

    def test_email_anonymization(self):
        resp = PrivacyService.test_anonymization("email", "zhang@company.com")
        assert resp.anonymized == "zha***@company.com"
        assert resp.method == "前缀掩码"

    def test_address_anonymization(self):
        resp = PrivacyService.test_anonymization("address", "上海市浦东新区张江路123号")
        assert resp.anonymized == "上海市浦东新区***"
        assert resp.method == "部分截断"

    def test_phone_no_match_keeps_value(self):
        # 不匹配手机号正则的输入应保持原值（re.sub 不替换）
        resp = PrivacyService.test_anonymization("phone", "abc")
        assert resp.anonymized == "abc"

    def test_unknown_field_uses_default_mask_short(self):
        # 短于等于 2 字符的值用全 * 替换
        resp = PrivacyService.test_anonymization("unknown_field", "ab")
        assert resp.anonymized == "**"
        assert resp.method == "默认掩码"

    def test_unknown_field_uses_default_mask_single(self):
        resp = PrivacyService.test_anonymization("unknown_field", "a")
        assert resp.anonymized == "*"

    def test_unknown_field_uses_default_mask_long(self):
        # 长于 2 字符保留前 2 位，其余 *
        resp = PrivacyService.test_anonymization("unknown_field", "hello")
        assert resp.anonymized == "he***"
        assert resp.method == "默认掩码"

    def test_empty_value(self):
        resp = PrivacyService.test_anonymization("anything", "")
        assert resp.original == ""
        assert resp.method in ("默认掩码", "部分掩码", "中间掩码", "首尾保留", "前缀掩码", "部分截断")


class TestComplianceItems:
    """合规检查项测试"""

    def test_returns_five_items(self):
        items = PrivacyService.get_compliance_items()
        assert len(items) == 5

    def test_each_item_has_required_fields(self):
        items = PrivacyService.get_compliance_items()
        for it in items:
            assert it.id
            assert it.category
            assert it.requirement
            assert it.status in ("pass", "pending", "fail")
            assert it.last_check
            assert it.detail

    def test_item_ids_unique(self):
        items = PrivacyService.get_compliance_items()
        ids = [it.id for it in items]
        assert len(ids) == len(set(ids))


class TestPermissionConfig:
    def test_returns_three_roles(self):
        perms = PrivacyService.get_permission_config()
        assert len(perms) == 3
        roles = [p.role for p in perms]
        assert "系统管理员" in roles
        assert "普通用户" in roles

    def test_admin_has_delete_permission(self):
        perms = PrivacyService.get_permission_config()
        admin = next(p for p in perms if p.role == "系统管理员")
        assert admin.export_allowed is True
        assert admin.delete_allowed is True

    def test_normal_user_has_no_export(self):
        perms = PrivacyService.get_permission_config()
        user = next(p for p in perms if p.role == "普通用户")
        assert user.export_allowed is False
        assert user.delete_allowed is False


class TestOverview:
    def test_overview_counts_rules_and_pending(self):
        overview = PrivacyService.get_overview()
        assert overview.anonymization_rule_count == 5
        assert overview.encryption_standard == "AES-256"
        assert overview.compliance_status in ("compliant", "warning")
        # pending_count 应等于非 pass 项的数量
        items = PrivacyService.get_compliance_items()
        expected_pending = sum(1 for it in items if it.status != "pass")
        assert overview.pending_count == expected_pending

    def test_overview_status_matches_pending(self):
        overview = PrivacyService.get_overview()
        if overview.pending_count == 0:
            assert overview.compliance_status == "compliant"
        else:
            assert overview.compliance_status == "warning"


class TestKeyInfo:
    def test_returns_one_key_entry(self):
        keys = PrivacyService.get_key_info()
        assert len(keys) == 1
        assert keys[0].algorithm == "HS256"

    def test_masked_value_contains_stars(self):
        keys = PrivacyService.get_key_info()
        assert "*" in keys[0].masked_value
