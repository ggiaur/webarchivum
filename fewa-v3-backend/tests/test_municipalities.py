import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from app.api.v1.municipalities import router as municipalities_router

app = FastAPI()
app.include_router(municipalities_router)

client = TestClient(app)


def test_list_active_municipalities():
    response = client.get("/api/municipalities")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert len(data) > 0
    # Ensure inactive ones are omitted by default
    slugs = [m["slug"] for m in data]
    assert "szekesfehervar" in slugs
    assert "szabadbattyan" not in slugs

    # Ensure correct sort order
    sort_orders = [m["sort_order"] for m in data]
    assert sort_orders == sorted(sort_orders)


def test_list_all_municipalities_include_inactive():
    response = client.get("/api/municipalities?include_inactive=true")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    slugs = [m["slug"] for m in data]
    assert "szabadbattyan" in slugs
