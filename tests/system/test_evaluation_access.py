from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.dependencies import auth
from app.models.user import User
from app.routers import evaluations
from app.services.auth_service import AuthService


def _user(*, is_admin: bool) -> User:
    return User(
        username="operator",
        email="operator@example.com",
        hashed_password="unused",
        is_admin=is_admin,
    )


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(evaluations.router, prefix="/api/evaluations")
    return TestClient(app)


def _authorization() -> dict[str, str]:
    token = AuthService.create_access_token(sub="operator")
    return {"Authorization": f"Bearer {token}"}


def test_evaluation_management_requires_authentication() -> None:
    response = _client().get("/api/evaluations/admin/access")

    assert response.status_code == 401


def test_evaluation_management_rejects_latest_non_admin_user(monkeypatch) -> None:
    async def get_latest_user(_username: str) -> User:
        return _user(is_admin=False)

    monkeypatch.setattr(
        auth.user_service,
        "get_user_by_username",
        get_latest_user,
    )

    response = _client().get(
        "/api/evaluations/admin/access",
        headers=_authorization(),
    )

    assert response.status_code == 403


def test_evaluation_management_accepts_latest_admin_user(monkeypatch) -> None:
    async def get_latest_user(_username: str) -> User:
        return _user(is_admin=True)

    monkeypatch.setattr(
        auth.user_service,
        "get_user_by_username",
        get_latest_user,
    )

    response = _client().get(
        "/api/evaluations/admin/access",
        headers=_authorization(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "data": {"can_manage": True},
        "message": "管理员权限验证成功",
    }
