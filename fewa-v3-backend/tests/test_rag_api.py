import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from app.api.v1.rag import router as rag_router

app = FastAPI()
app.include_router(rag_router)

client = TestClient(app)


def test_rag_query_sufficient_confidence():
    response = client.post(
        "/api/rag",
        json={"question": "Hol található a Vörösmarty Mihály Könyvtár?"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["is_sufficient"] is True
    assert data["confidence_score"] >= 0.6
    assert "Könyvtár" in data["answer"]
    assert "warning" in data
    assert "trace_id" in data
    assert len(data["sources"]) >= 1


def test_rag_query_insufficient_confidence_guardrail():
    response = client.post(
        "/api/rag",
        json={"question": "Ismeretlen irreleváns kérdés amire nincs adat?"},
    )
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["is_sufficient"] is False
    assert data["confidence_score"] < 0.6
    assert data["answer"] == "Nincs elegendő bizonyíték az archívumban."


def test_rag_feedback_success():
    # Query first to get trace_id
    query_res = client.post(
        "/api/rag",
        json={"question": "Hol található a Vörösmarty Mihály Könyvtár?"},
    )
    trace_id = query_res.json()["trace_id"]

    # Submit feedback
    fb_res = client.post(
        "/api/rag/feedback",
        json={"trace_id": trace_id, "feedback": "helpful", "note": "Pontos válasz"},
    )
    assert fb_res.status_code == status.HTTP_204_NO_CONTENT
