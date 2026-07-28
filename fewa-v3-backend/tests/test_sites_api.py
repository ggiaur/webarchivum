import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from app.api.v1.sites import router as sites_router
from app.core.security import create_access_token

app = FastAPI()
app.include_router(sites_router)

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


def test_list_sites_requires_archivist_role():
    # Curator is not enough for sites CRUD (requires archivist+)
    res_curator = client.get(
        "/api/admin/sites",
        headers={"Authorization": f"Bearer {CURATOR_TOKEN}"},
    )
    assert res_curator.status_code == status.HTTP_403_FORBIDDEN

    # Archivist should succeed
    res_archivist = client.get(
        "/api/admin/sites",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
    )
    assert res_archivist.status_code == status.HTTP_200_OK
    assert "items" in res_archivist.json()


def test_create_and_get_site_success():
    payload = {
        "domain": "fejer.hu",
        "base_url": "https://fejer.hu",
        "display_name": "Fejér Vármegyei Önkormányzat",
        "priority": "critical",
        "category": "közintézmény",
        "crawl_frequency": "daily",
        "curator_notes": "Napi mentés kiemelten fontos",
        "oszk_status": "yes",
    }
    response = client.post(
        "/api/admin/sites",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
        json=payload,
    )
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    site_id = data["id"]
    assert data["domain"] == "fejer.hu"
    assert data["priority"] == "critical"

    # Get site detail
    get_res = client.get(
        f"/api/admin/sites/{site_id}",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
    )
    assert get_res.status_code == status.HTTP_200_OK
    assert get_res.json()["domain"] == "fejer.hu"


def test_create_duplicate_domain_returns_409():
    payload = {
        "domain": "alba.hu",  # Already exists in mock DB
        "base_url": "https://alba.hu",
    }
    response = client.post(
        "/api/admin/sites",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
        json=payload,
    )
    assert response.status_code == status.HTTP_409_CONFLICT


def test_update_site_success():
    # Update alba.hu site
    site_id = "550e8400-e29b-41d4-a716-446655440001"
    patch_res = client.patch(
        f"/api/admin/sites/{site_id}",
        headers={"Authorization": f"Bearer {ARCHIVIST_TOKEN}"},
        json={"priority": "critical", "curator_notes": "Módosított megjegyzés"},
    )
    assert patch_res.status_code == status.HTTP_200_OK
    updated = patch_res.json()
    assert updated["priority"] == "critical"
    assert updated["curator_notes"] == "Módosított megjegyzés"
