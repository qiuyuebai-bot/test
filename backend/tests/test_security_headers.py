"""P0-5 加固回归测试：验证安全响应头中间件正确注入 CSP 等安全头"""
import pytest
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


@pytest.fixture(scope="module")
def client():
    """模块级复用：仅构建一次应用与客户端，避免每个用例重复装配"""
    return TestClient(_build_app())


@pytest.mark.parametrize(
    "header, must_contain, must_equal",
    [
        pytest.param(
            "content-security-policy",
            ["default-src 'self'", "object-src 'none'", "frame-ancestors 'none'"],
            None,
            id="csp-default-directives",
        ),
        pytest.param(
            "x-content-type-options",
            [],
            "nosniff",
            id="x-content-type-options-nosniff",
        ),
        pytest.param(
            "x-frame-options",
            [],
            "DENY",
            id="x-frame-options-deny",
        ),
        pytest.param(
            "strict-transport-security",
            ["max-age=31536000", "includeSubDomains"],
            None,
            id="hsts",
        ),
        pytest.param(
            "referrer-policy",
            [],
            "strict-origin-when-cross-origin",
            id="referrer-policy",
        ),
        pytest.param(
            "permissions-policy",
            ["geolocation=()", "microphone=()", "camera=()"],
            None,
            id="permissions-policy",
        ),
        pytest.param(
            "content-security-policy",
            ["style-src 'self' 'unsafe-inline'"],
            None,
            id="csp-allows-inline-styles",
        ),
        pytest.param(
            "content-security-policy",
            ["img-src 'self' data: blob:"],
            None,
            id="csp-allows-data-uri-images",
        ),
    ],
)
def test_security_headers_on_success_response(client, header, must_contain, must_equal):
    """成功响应应注入全部安全头（参数化覆盖各头部精确值与子串断言）"""
    resp = client.get("/ping")
    assert resp.status_code == 200
    value = resp.headers.get(header, "")
    if must_equal is not None:
        assert value == must_equal
    for substring in must_contain:
        assert substring in value


def test_security_headers_on_error_response():
    """错误响应也应包含安全头"""
    client = TestClient(_build_app())
    resp = client.get("/nonexistent")
    assert resp.status_code == 404
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert "default-src 'self'" in resp.headers.get("content-security-policy", "")
