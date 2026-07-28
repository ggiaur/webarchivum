import pytest
from fastapi import FastAPI, Depends, status
from fastapi.testclient import TestClient
from app.api.deps import require_role
from app.core.security import create_access_token

app = FastAPI()


@app.get("/api/public")
def public_endpoint():
    return {"message": "public"}


@app.get("/api/admin/queue", dependencies=[Depends(require_role("curator"))])
def curator_endpoint():
    return {"message": "curator_approved"}


client = TestClient(app)


def test_public_endpoint_accessible():
    response = client.get("/api/public")
    assert response.status_code == status.HTTP_200_OK


def test_protected_endpoint_no_token_returns_401():
    response = client.get("/api/admin/queue")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_protected_endpoint_insufficient_role_returns_403():
    viewer_token = create_access_token(
        subject="user-123",
        role="viewer",
        tenant_id="00000000-0000-0000-0000-000000000001",
    )
    headers = {"Authorization": f"Bearer {viewer_token}"}
    response = client.get("/api/admin/queue", headers=headers)
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_protected_endpoint_sufficient_role_returns_200():
    curator_token = create_access_token(
        subject="user-456",
        role="curator",
        tenant_id="00000000-0000-0000-0000-000000000001",
    )
    headers = {"Authorization": f"Bearer {curator_token}"}
    response = client.get("/api/admin/queue", headers=headers)
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["message"] == "curator_approved"
