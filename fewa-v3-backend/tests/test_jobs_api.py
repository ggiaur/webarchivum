import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from app.api.v1.jobs import router as jobs_router
from app.core.security import create_access_token

app = FastAPI()
app.include_router(jobs_router)

client = TestClient(app)

ARCHIVIST_TOKEN = create_access_token(
    subject="archivist-user",
    role="archivist",
    tenant_id="00000000-0000-0000-0000-000000000001",
)
CURATOR_TOKEN = create_access_token(
    subject="curator-user",
    role="curator",
    tenant_id="00000000-0000-0000-0000-000000000001",
)


def test_trigger_ingest_unknown_site_returns_404():
    response = client.post(
        "/api/admin/ingest",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
        json={"site_id": "nonexistent-site-id"},
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_trigger_ingest_success_returns_202():
    # Existing site in mock DB
    site_id = "550e8400-e29b-41d4-a716-446655440001"
    response = client.post(
        "/api/admin/ingest",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
        json={"site_id": site_id},
    )
    assert response.status_code == status.HTTP_202_ACCEPTED
    data = response.json()
    assert data["job_type"] == "crawl"
    assert data["status"] == "queued"
    assert "id" in data


def test_list_jobs():
    response = client.get(
        "/api/admin/jobs",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
    )
    assert response.status_code == status.HTTP_200_OK
    assert "items" in response.json()
