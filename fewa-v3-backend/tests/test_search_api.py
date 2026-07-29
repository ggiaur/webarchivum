import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from app.api.v1.search import router as search_router

app = FastAPI()
app.include_router(search_router)

client = TestClient(app)


def test_search_valid_query_returns_200():
    response = client.get("/api/search?q=Városháza")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert "results" in data
    assert data["search_type"] == "hybrid"
    assert data["total"] >= 1
    assert data["query_time_ms"] >= 0


def test_search_short_query_returns_200():
    response = client.get("/api/search?q=a")
    assert response.status_code == status.HTTP_200_OK


def test_search_municipality_filter():
    response = client.get("/api/search?q=Könyvtár&municipality_slug=szekesfehervar")
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    for res in data["results"]:
        assert res["municipality"]["slug"] == "szekesfehervar"
