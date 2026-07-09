"""
审计日志系统测试
- 中间件自动记录写操作
- 查询API（管理员权限）
- 统计API
"""
import pytest
from app.models.audit_log import AuditLog


class TestAuditMiddleware:
    """审计中间件自动记录测试"""

    def test_login_creates_audit_log(self, client, db_session, sample_admin_user):
        """登录操作应自动记录审计日志"""
        response = client.post("/api/v1/auth/login", json={
            "username": "admin_user",
            "password": "admin_password",
        })
        assert response.status_code == 200

        logs = db_session.query(AuditLog).filter(
            AuditLog.action == "LOGIN"
        ).all()
        assert len(logs) >= 1
        log = logs[-1]
        assert log.method == "POST"
        assert "/auth/login" in log.path
        assert log.status_code == 200
        # TestClient 不设置 request.client，ip_address 可能为 None
        assert log.duration_ms is not None

    def test_write_operation_audited(self, client, admin_auth_headers, db_session, sample_admin_user):
        """写操作（POST/PUT/DELETE）应记录审计日志"""
        response = client.post(
            "/api/v1/learners",
            json={
                "user_id": sample_admin_user.id,
                "real_name": "审计测试用户",
                "display_name": "AuditTest001",
                "education_level": "master",
                "major": "计算机科学",
                "school": "测试大学",
                "graduation_year": 2020,
                "current_position": "开发工程师",
                "years_of_experience": 2,
            },
            headers=admin_auth_headers,
        )
        assert response.status_code in (200, 201)

        logs = db_session.query(AuditLog).filter(
            AuditLog.action == "CREATE",
            AuditLog.resource_type == "learner",
        ).all()
        assert len(logs) >= 1
        log = logs[-1]
        assert log.method == "POST"
        assert "/learners" in log.path
        assert log.status_code in (200, 201)

    def test_health_check_not_audited(self, client, db_session):
        """健康检查不应记录审计日志"""
        response = client.get("/health")
        assert response.status_code == 200

        logs = db_session.query(AuditLog).filter(
            AuditLog.path == "/health"
        ).all()
        assert len(logs) == 0

    def test_options_not_audited(self, client, db_session):
        """OPTIONS预检请求不应记录审计日志"""
        response = client.options("/api/v1/learners")
        # OPTIONS 返回 405 或 200 都正常
        assert response.status_code in (200, 405)

        logs = db_session.query(AuditLog).filter(
            AuditLog.method == "OPTIONS"
        ).all()
        assert len(logs) == 0

    def test_user_info_extracted_from_token(self, client, admin_auth_headers, db_session, sample_admin_user):
        """带Token的请求应提取用户信息"""
        response = client.post(
            "/api/v1/learners",
            json={
                "user_id": sample_admin_user.id,
                "real_name": "Token提取测试",
                "display_name": "TokenTest001",
                "education_level": "bachelor",
                "major": "软件工程",
                "school": "测试大学",
                "graduation_year": 2021,
                "current_position": "后端工程师",
                "years_of_experience": 1,
            },
            headers=admin_auth_headers,
        )
        assert response.status_code in (200, 201)

        logs = db_session.query(AuditLog).filter(
            AuditLog.action == "CREATE",
            AuditLog.resource_type == "learner",
        ).all()
        assert len(logs) >= 1
        log = logs[-1]
        assert log.user_id == sample_admin_user.id
        assert log.username == sample_admin_user.username


class TestAuditQueryAPI:
    """审计日志查询API测试"""

    def test_get_logs_requires_admin(self, client, auth_headers):
        """非管理员不能查询审计日志"""
        response = client.get("/api/v1/audit/logs", headers=auth_headers)
        assert response.status_code == 403

    def test_get_logs_requires_auth(self, client):
        """未登录不能查询审计日志"""
        response = client.get("/api/v1/audit/logs")
        assert response.status_code == 401

    def test_get_logs_success(self, client, admin_auth_headers, db_session):
        """管理员可分页查询审计日志"""
        for i in range(5):
            log = AuditLog(
                user_id=1,
                username="test_user",
                action="CREATE",
                resource_type="learner",
                method="POST",
                path=f"/api/v1/learners",
                status_code=200,
                ip_address="127.0.0.1",
                duration_ms=50,
            )
            db_session.add(log)
        db_session.commit()

        response = client.get(
            "/api/v1/audit/logs?page=1&page_size=3",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["total"] >= 5
        assert len(data["data"]["items"]) == 3
        assert data["data"]["page"] == 1
        assert data["data"]["page_size"] == 3

    def test_filter_by_action(self, client, admin_auth_headers, db_session):
        """按操作类型筛选"""
        db_session.add(AuditLog(
            action="LOGIN", method="POST", path="/auth/login", status_code=200,
        ))
        db_session.add(AuditLog(
            action="DELETE", method="DELETE", path="/learners/1", status_code=200,
        ))
        db_session.commit()

        response = client.get(
            "/api/v1/audit/logs?action=LOGIN",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        for item in data["data"]["items"]:
            assert item["action"] == "LOGIN"

    def test_stats_requires_admin(self, client, auth_headers):
        """非管理员不能查看统计"""
        response = client.get("/api/v1/audit/stats", headers=auth_headers)
        assert response.status_code == 403

    def test_stats_success(self, client, admin_auth_headers, db_session):
        """管理员可查看审计统计"""
        db_session.add(AuditLog(
            action="CREATE", method="POST", path="/learners", status_code=200,
            user_id=1, username="admin",
        ))
        db_session.add(AuditLog(
            action="DELETE", method="DELETE", path="/learners/1", status_code=200,
            user_id=1, username="admin",
        ))
        db_session.add(AuditLog(
            action="CREATE", method="POST", path="/knowledge/upload", status_code=500,
            user_id=2, username="teacher1",
        ))
        db_session.commit()

        response = client.get(
            "/api/v1/audit/stats?days=30",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert data["data"]["total"] >= 3
        assert data["data"]["errors"] >= 1
        assert data["data"]["error_rate"] > 0
        assert len(data["data"]["actions"]) > 0

    def test_get_actions(self, client, admin_auth_headers, db_session):
        """获取操作类型列表"""
        db_session.add(AuditLog(
            action="LOGIN", method="POST", path="/auth/login", status_code=200,
        ))
        db_session.commit()

        response = client.get(
            "/api/v1/audit/actions",
            headers=admin_auth_headers,
        )
        assert response.status_code == 200
        data = response.json()
        assert data["code"] == 200
        assert "LOGIN" in data["data"]
