"""
认证模块单元测试
测试范围：JWT Token生成/验证、密码哈希、登录/注册接口、鉴权依赖
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import User, UserRoleEnum
from app.utils.auth import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_access_token,
    verify_refresh_token,
    create_tokens_for_user,
    CurrentUser,
    get_current_user,
)
from app.schemas.auth import LoginRequest, RegisterRequest, ChangePasswordRequest


# ===========================================
# 密码哈希测试
# ===========================================

class TestPasswordHashing:
    """密码哈希与验证测试"""

    def test_hash_password(self):
        """测试密码哈希"""
        password = "test_password_123"
        hashed = hash_password(password)
        
        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt格式

    def test_verify_password_correct(self):
        """测试正确密码验证"""
        password = "correct_password"
        hashed = hash_password(password)
        
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """测试错误密码验证"""
        password = "correct_password"
        hashed = hash_password(password)
        
        assert verify_password("wrong_password", hashed) is False

    def test_different_hashes_for_same_password(self):
        """测试相同密码生成不同哈希（加盐）"""
        password = "same_password"
        hash1 = hash_password(password)
        hash2 = hash_password(password)
        
        assert hash1 != hash2
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


# ===========================================
# JWT Token 测试
# ===========================================

class TestJWTToken:
    """JWT Token生成与验证测试"""

    def test_create_access_token(self):
        """测试创建访问Token"""
        token_data = {"user_id": 1, "username": "test", "role": "learner"}
        token = create_access_token(token_data)
        
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token(self):
        """测试创建刷新Token"""
        token_data = {"user_id": 1, "username": "test"}
        token = create_refresh_token(token_data)
        
        assert token is not None
        assert isinstance(token, str)

    def test_decode_token(self):
        """测试解码Token"""
        token_data = {"user_id": 1, "username": "test", "role": "learner"}
        token = create_access_token(token_data)
        payload = decode_token(token)
        
        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["username"] == "test"
        assert payload["role"] == "learner"
        assert payload["type"] == "access"
        assert "exp" in payload
        assert "iat" in payload

    def test_verify_access_token(self):
        """测试验证访问Token"""
        token_data = {"user_id": 1, "username": "test"}
        token = create_access_token(token_data)
        payload = verify_access_token(token)
        
        assert payload is not None
        assert payload["user_id"] == 1

    def test_verify_refresh_token(self):
        """测试验证刷新Token"""
        token_data = {"user_id": 1}
        token = create_refresh_token(token_data)
        payload = verify_refresh_token(token)
        
        assert payload is not None
        assert payload["user_id"] == 1
        assert payload["type"] == "refresh"

    def test_access_token_not_accepted_as_refresh(self):
        """测试访问Token不被当作刷新Token"""
        token_data = {"user_id": 1}
        token = create_access_token(token_data)
        payload = verify_refresh_token(token)
        
        assert payload is None

    def test_refresh_token_not_accepted_as_access(self):
        """测试刷新Token不被当作访问Token"""
        token_data = {"user_id": 1}
        token = create_refresh_token(token_data)
        payload = verify_access_token(token)
        
        assert payload is None

    def test_invalid_token(self):
        """测试无效Token"""
        assert decode_token("invalid_token_123") is None
        assert verify_access_token("invalid_token") is None
        assert verify_refresh_token("invalid_token") is None

    def test_empty_token(self):
        """测试空Token"""
        assert decode_token("") is None
        assert verify_access_token("") is None

    def test_create_tokens_for_user(self, sample_user: User):
        """测试为用户创建Token对"""
        tokens = create_tokens_for_user(sample_user)
        
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"
        assert len(tokens["access_token"]) > 0
        assert len(tokens["refresh_token"]) > 0

    def test_token_contains_user_info(self, sample_user: User):
        """测试Token包含用户信息"""
        tokens = create_tokens_for_user(sample_user)
        payload = verify_access_token(tokens["access_token"])
        
        assert payload["user_id"] == sample_user.id
        assert payload["username"] == sample_user.username


# ===========================================
# CurrentUser 测试
# ===========================================

class TestCurrentUser:
    """CurrentUser类测试"""

    def test_current_user_properties(self):
        """测试CurrentUser属性"""
        user = CurrentUser(user_id=1, username="test", role="learner")
        
        assert user.user_id == 1
        assert user.username == "test"
        assert user.role == "learner"
        assert user.is_learner is True
        assert user.is_admin is False
        assert user.is_teacher is False
        assert user.is_enterprise is False

    def test_current_user_admin(self):
        """测试管理员CurrentUser"""
        user = CurrentUser(user_id=1, username="admin", role="admin")
        
        assert user.is_admin is True
        assert user.is_learner is False

    def test_has_role(self):
        """测试角色检查"""
        user = CurrentUser(user_id=1, username="test", role="learner")
        
        assert user.has_role("learner") is True
        assert user.has_role("admin") is False
        assert user.has_role("learner", "teacher") is True
        assert user.has_role("admin", "teacher") is False


# ===========================================
# Schema 验证测试
# ===========================================

class TestAuthSchemas:
    """认证Schema验证测试"""

    def test_login_request_valid(self):
        """测试登录请求验证"""
        req = LoginRequest(username="test_user", password="pass123")
        assert req.username == "test_user"
        assert req.password == "pass123"

    def test_login_request_username_too_short(self):
        """测试用户名太短"""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            LoginRequest(username="ab", password="pass123")

    def test_register_request_valid(self):
        """测试注册请求验证"""
        req = RegisterRequest(
            username="new_user",
            password="password123",
            email="user@example.com",
        )
        assert req.username == "new_user"
        assert req.email == "user@example.com"

    def test_register_request_invalid_username(self):
        """测试非法用户名"""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RegisterRequest(
                username="user name!",
                password="password123",
            )

    def test_register_request_invalid_email(self):
        """测试非法邮箱"""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            RegisterRequest(
                username="valid_user",
                password="password123",
                email="invalid-email",
            )

    def test_change_password_weak_password(self):
        """测试弱密码"""
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            ChangePasswordRequest(
                old_password="old_pass",
                new_password="12345678",  # 只有数字，没有字母
            )

    def test_change_password_valid(self):
        """测试有效修改密码请求"""
        req = ChangePasswordRequest(
            old_password="old_pass123",
            new_password="new_pass123",
        )
        assert req.old_password == "old_pass123"
        assert req.new_password == "new_pass123"


# ===========================================
# API 接口集成测试
# ===========================================

class TestAuthAPI:
    """认证API接口测试"""

    def test_register_success(self, client: TestClient):
        """测试注册成功"""
        response = client.post("/api/v1/auth/register", json={
            "username": "new_test_user",
            "password": "password123",
            "email": "newuser@test.com",
            "role": "learner",
        })
        data = response.json()
        
        assert response.status_code == 200
        assert data["code"] == 200
        assert data["data"]["username"] == "new_test_user"
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]

    def test_register_duplicate_username(self, client: TestClient, sample_user: User):
        """测试重复用户名注册"""
        response = client.post("/api/v1/auth/register", json={
            "username": sample_user.username,  # 已存在
            "password": "password123",
        })
        data = response.json()
        
        assert data["code"] == 400

    def test_login_success(self, client: TestClient, sample_user: User):
        """测试登录成功"""
        response = client.post("/api/v1/auth/login", json={
            "username": sample_user.username,
            "password": "test_password",
        })
        data = response.json()
        
        assert response.status_code == 200
        assert data["code"] == 200
        assert data["data"]["username"] == sample_user.username
        assert "access_token" in data["data"]
        assert "refresh_token" in data["data"]

    def test_login_wrong_password(self, client: TestClient, sample_user: User):
        """测试错误密码登录"""
        response = client.post("/api/v1/auth/login", json={
            "username": sample_user.username,
            "password": "wrong_password",
        })
        data = response.json()
        
        assert data["code"] == 401

    def test_login_nonexistent_user(self, client: TestClient):
        """测试不存在的用户登录"""
        response = client.post("/api/v1/auth/login", json={
            "username": "nonexistent",
            "password": "password",
        })
        data = response.json()
        
        assert data["code"] == 401

    def test_refresh_token(self, client: TestClient, sample_user: User):
        """测试刷新Token"""
        tokens = create_tokens_for_user(sample_user)
        
        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": tokens["refresh_token"],
        })
        data = response.json()
        
        assert response.status_code == 200
        assert data["code"] == 200
        assert "access_token" in data["data"]

    def test_refresh_token_invalid(self, client: TestClient):
        """测试无效刷新Token"""
        response = client.post("/api/v1/auth/refresh", json={
            "refresh_token": "invalid_token",
        })
        data = response.json()
        
        assert data["code"] == 401

    def test_get_me_authenticated(self, client: TestClient, sample_user: User, auth_headers: dict):
        """测试获取当前用户信息（已认证）"""
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        data = response.json()
        
        assert response.status_code == 200
        assert data["code"] == 200
        assert data["data"]["user_id"] == sample_user.id
        assert data["data"]["username"] == sample_user.username

    def test_get_me_unauthenticated(self, client: TestClient):
        """测试获取当前用户信息（未认证）"""
        response = client.get("/api/v1/auth/me")
        
        assert response.status_code == 401

    def test_verify_token_valid(self, client: TestClient, auth_headers: dict):
        """测试验证有效Token"""
        response = client.get("/api/v1/auth/verify", headers=auth_headers)
        data = response.json()
        
        assert response.status_code == 200
        assert data["data"]["valid"] is True

    def test_verify_token_invalid(self, client: TestClient):
        """测试验证无效Token"""
        response = client.get("/api/v1/auth/verify", headers={
            "Authorization": "Bearer invalid_token_here"
        })
        
        assert response.status_code == 401

    def test_logout(self, client: TestClient, auth_headers: dict):
        """测试登出"""
        response = client.post("/api/v1/auth/logout", headers=auth_headers)
        data = response.json()
        
        assert response.status_code == 200
        assert data["code"] == 200

    def test_change_password(self, client: TestClient, sample_user: User, auth_headers: dict):
        """测试修改密码"""
        response = client.post("/api/v1/auth/change-password", headers=auth_headers, json={
            "old_password": "test_password",
            "new_password": "new_password123",
        })
        data = response.json()
        
        assert response.status_code == 200
        assert data["code"] == 200

    def test_change_password_wrong_old(self, client: TestClient, auth_headers: dict):
        """测试旧密码错误"""
        response = client.post("/api/v1/auth/change-password", headers=auth_headers, json={
            "old_password": "wrong_old_password",
            "new_password": "new_password123",
        })
        data = response.json()
        
        assert data["code"] == 400

    def test_protected_route_without_auth(self, client: TestClient):
        """测试未认证访问受保护路由"""
        response = client.get("/api/v1/learners")
        
        # 当前learner路由未强制鉴权，但detail路由需要
        response = client.get("/api/v1/learners/1")
        assert response.status_code == 401

    def test_protected_route_with_auth(self, client: TestClient, auth_headers: dict):
        """测试认证后访问受保护路由"""
        response = client.get("/api/v1/agent/status", headers=auth_headers)
        
        assert response.status_code == 200
        assert response.json()["code"] == 200


# ===========================================
# 边界条件测试
# ===========================================

class TestAuthEdgeCases:
    """认证边界条件测试"""

    def test_disabled_user_login(self, client: TestClient, db_session: Session, sample_user: User):
        """测试禁用用户登录"""
        # 禁用用户
        sample_user.is_active = False
        db_session.commit()
        
        response = client.post("/api/v1/auth/login", json={
            "username": sample_user.username,
            "password": "test_password",
        })
        data = response.json()
        
        assert data["code"] == 401

    def test_disabled_user_token_rejected(self, client: TestClient, db_session: Session, sample_user: User, auth_headers: dict):
        """测试禁用用户的Token被拒绝"""
        # 先禁用用户
        sample_user.is_active = False
        db_session.commit()
        
        response = client.get("/api/v1/auth/me", headers=auth_headers)
        
        assert response.status_code == 401

    def test_expired_token(self, client: TestClient, sample_user: User):
        """测试过期Token"""
        from datetime import timedelta
        from app.utils.auth import create_access_token
        
        token_data = {
            "user_id": sample_user.id,
            "username": sample_user.username,
            "role": "learner",
        }
        # 创建已过期的Token
        expired_token = create_access_token(token_data, expires_delta=timedelta(seconds=-1))
        
        response = client.get("/api/v1/auth/me", headers={
            "Authorization": f"Bearer {expired_token}"
        })
        
        assert response.status_code == 401

    def test_malformed_token(self, client: TestClient):
        """测试格式错误的Token"""
        response = client.get("/api/v1/auth/me", headers={
            "Authorization": "NotBearer token"
        })
        
        assert response.status_code == 401