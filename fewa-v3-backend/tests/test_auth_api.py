import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from app.api.v1.auth import router as auth_router

app = FastAPI()
app.include_router(auth_router)

client = TestClient(app)


def test_login_success():
    response = client.post(
        "/api/auth/login",
        json={
            "email": "curator@vmk.hu",
            "password": "SecretPassword123!",
        },
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["role"] == "curator"


def test_login_invalid_password_fails():
    response = client.post(
        "/api/auth/login",
        json={
            "email": "curator@vmk.hu",
            "password": "WrongPassword",
        },
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Érvénytelen" in response.json()["detail"]


def test_login_unknown_user_fails():
    response = client.post(
        "/api/auth/login",
        json={
            "email": "nonexistent@vmk.hu",
            "password": "SecretPassword123!",
        },
    )
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_refresh_token_success():
    # Login first
    login_res = client.post(
        "/api/auth/login",
        json={
            "email": "curator@vmk.hu",
            "password": "SecretPassword123!",
        },
    )
    refresh_token = login_res.json()["refresh_token"]

    # Refresh
    response = client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data


def test_logout_and_subsequent_refresh_fails():
    # Login
    login_res = client.post(
        "/api/auth/login",
        json={
            "email": "curator@vmk.hu",
            "password": "SecretPassword123!",
        },
    )
    access_token = login_res.json()["access_token"]
    refresh_token = login_res.json()["refresh_token"]

    # Logout with auth header
    logout_res = client.post(
        "/api/auth/logout",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"refresh_token": refresh_token},
    )
    assert logout_res.status_code == status.HTTP_204_NO_CONTENT

    # Try refreshing using revoked token
    refresh_res = client.post(
        "/api/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert refresh_res.status_code == status.HTTP_401_UNAUTHORIZED
