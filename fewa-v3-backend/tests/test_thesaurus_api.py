import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from app.api.v1.thesaurus import router as thesaurus_router
from app.core.security import create_access_token

app = FastAPI()
app.include_router(thesaurus_router)

client = TestClient(app)

VIEWER_TOKEN = create_access_token(
    subject="viewer-user",
    role="viewer",
    tenant_id="00000000-0000-0000-0000-000000000001",
)
CURATOR_TOKEN = create_access_token(
    subject="curator-user",
    role="curator",
    tenant_id="00000000-0000-0000-0000-000000000001",
)


def test_list_thesaurus_requires_viewer_role():
    # Unauthenticated request fails
    res_anon = client.get("/api/thesaurus")
    assert res_anon.status_code == status.HTTP_401_UNAUTHORIZED

    # Viewer succeeds
    res_viewer = client.get(
        "/api/thesaurus",
        headers={"Authorization": f"Bearer {VIEWER_TOKEN}"},
    )
    assert res_viewer.status_code == status.HTTP_200_OK
    assert "items" in res_viewer.json()


def test_search_thesaurus_query():
    response = client.get(
        "/api/thesaurus?q=politika",
        headers={"Authorization": f"Bearer {VIEWER_TOKEN}"},
    )
    assert response.status_code == status.HTTP_200_OK
    items = response.json()["items"]
    assert len(items) >= 1
    assert "politika" in items[0]["pref_label_hu"].lower()


def test_create_and_patch_thesaurus_concept():
    # Viewer cannot create concept (requires curator+)
    create_fail = client.post(
        "/api/thesaurus",
        headers={"Authorization": f"Bearer {VIEWER_TOKEN}"},
        json={"pref_label_hu": "környezetvédelem"},
    )
    assert create_fail.status_code == status.HTTP_403_FORBIDDEN

    # Curator creates concept
    create_res = client.post(
        "/api/thesaurus",
        headers={"Authorization": f"Bearer {CURATOR_TOKEN}"},
        json={
            "pref_label_hu": "környezetvédelem",
            "alt_labels": ["ökológia", "zöld ügyek"],
            "definition": "Fejér vármegyei környezetvédelmi témák",
        },
    )
    assert create_res.status_code == status.HTTP_201_CREATED
    concept = create_res.json()
    concept_id = concept["id"]
    assert concept["pref_label_hu"] == "környezetvédelem"

    # Curator patches concept
    patch_res = client.patch(
        f"/api/thesaurus/{concept_id}",
        headers={"Authorization": f"Bearer {CURATOR_TOKEN}"},
        json={"notation": "KO-001"},
    )
    assert patch_res.status_code == status.HTTP_200_OK
    assert patch_res.json()["notation"] == "KO-001"
