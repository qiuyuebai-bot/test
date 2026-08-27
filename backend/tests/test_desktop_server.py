from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.database import get_db
from app.middleware.desktop_auth import DesktopAuthMiddleware
from app.models.user import User, UserRoleEnum
from app.routers import desktop as desktop_router_module
from app.routers.desktop import router as desktop_router


def test_desktop_token_and_first_admin_bootstrap(db_session, monkeypatch):
    app = FastAPI()
    app.add_middleware(DesktopAuthMiddleware, token="desktop-test-token")
    app.include_router(desktop_router, prefix="/api/v1")

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    monkeypatch.setattr(desktop_router_module, "init_learner_seed_data", lambda: None)
    monkeypatch.setattr(desktop_router_module, "init_knowledge_seed_data", lambda: None)

    with TestClient(app) as client:
        assert client.get("/api/v1/desktop/bootstrap-status").status_code == 403

        headers = {"X-Zhiyu-Desktop-Token": "desktop-test-token"}
        assert client.get("/api/v1/desktop/bootstrap-status", headers=headers).json()["data"] == {
            "required": True
        }
        weak = client.post(
            "/api/v1/desktop/bootstrap",
            headers=headers,
            json={"username": "owner", "password": "password"},
        )
        assert weak.status_code == 422

        created = client.post(
            "/api/v1/desktop/bootstrap",
            headers=headers,
            json={"username": "owner", "password": "Owner1234"},
        )
        assert created.status_code == 201
        assert created.json()["data"]["role"] == "admin"
        assert db_session.query(User).filter(User.role == UserRoleEnum.ADMIN).count() == 1
        assert client.post(
            "/api/v1/desktop/bootstrap",
            headers=headers,
            json={"username": "other", "password": "Other1234"},
        ).status_code == 409
