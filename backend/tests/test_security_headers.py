"""P0-5 加固回归测试：验证安全响应头中间件正确注入 CSP 等安全头"""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from app.middleware.security_headers import SecurityHeadersMiddleware


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/ping")
    def _ping():
        return {"ok": True}

    return app


def test_csp_header_present():
    """响应应包含 Content-Security-Policy 头"""
    client = TestClient(_build_app())
    resp = client.get("/ping")
    assert resp.status_code == 200
    csp = resp.headers.get("content-security-policy", "")
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp


def test_x_content_type_options_present():
    """响应应包含 X-Content-Type-Options: nosniff"""
    client = TestClient(_build_app())
    resp = client.get("/ping")
    assert resp.headers.get("x-content-type-options") == "nosniff"


def test_x_frame_options_present():
    """响应应包含 X-Frame-Options: DENY（防点击劫持）"""
    client = TestClient(_build_app())
    resp = client.get("/ping")
    assert resp.headers.get("x-frame-options") == "DENY"


def test_hsts_header_present():
    """响应应包含 Strict-Transport-Security（HSTS）"""
    client = TestClient(_build_app())
    resp = client.get("/ping")
    hsts = resp.headers.get("strict-transport-security", "")
    assert "max-age=31536000" in hsts
    assert "includeSubDomains" in hsts


def test_referrer_policy_present():
    """响应应包含 Referrer-Policy"""
    client = TestClient(_build_app())
    resp = client.get("/ping")
    assert resp.headers.get("referrer-policy") == "strict-origin-when-cross-origin"


def test_permissions_policy_present():
    """响应应包含 Permissions-Policy（限制敏感 API）"""
    client = TestClient(_build_app())
    resp = client.get("/ping")
    pp = resp.headers.get("permissions-policy", "")
    assert "geolocation=()" in pp
    assert "microphone=()" in pp
    assert "camera=()" in pp


def test_csp_allows_inline_styles_for_tailwind():
    """CSP 应允许 'unsafe-inline' 样式（Tailwind 兼容）"""
    client = TestClient(_build_app())
    resp = client.get("/ping")
    csp = resp.headers.get("content-security-policy", "")
    assert "style-src 'self' 'unsafe-inline'" in csp


def test_csp_allows_data_uri_for_images():
    """CSP 应允许 data: 图片源（前端内联图片）"""
    client = TestClient(_build_app())
    resp = client.get("/ping")
    csp = resp.headers.get("content-security-policy", "")
    assert "img-src 'self' data: blob:" in csp


def test_security_headers_on_error_response():
    """错误响应也应包含安全头"""
    client = TestClient(_build_app())
    resp = client.get("/nonexistent")
    assert resp.status_code == 404
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert "default-src 'self'" in resp.headers.get("content-security-policy", "")
