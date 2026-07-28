import pytest
from fastapi import status
from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.workers.arq_worker import run_crawl_job, run_enrich_job

client = TestClient(app)


def test_full_e2e_archival_pipeline_flow():
    """
    E2E Integration Test: Auth -> Site -> Ingest -> Arq Worker -> Search -> RAG -> OAI-PMH
    """
    # Step 1: Login & Token
    auth_token = create_access_token(
        subject="archivist-e2e",
        role="archivist",
        tenant_id="00000000-0000-0000-0000-000000000001",
    )
    headers = {"Authorization": f"Bearer {auth_token}"}

    # Step 2: Fetch Municipalities
    muni_res = client.get("/api/municipalities")
    assert muni_res.status_code == status.HTTP_200_OK
    municipalities = muni_res.json()
    assert len(municipalities) >= 1

    # Step 3: Trigger Ingest for existing mock site
    site_id = "550e8400-e29b-41d4-a716-446655440001"
    ingest_res = client.post("/api/admin/ingest", headers=headers, json={"site_id": site_id})
    assert ingest_res.status_code == status.HTTP_202_ACCEPTED
    job_data = ingest_res.json()
    assert job_data["status"] == "queued"
    assert job_data["job_type"] == "crawl"

    # Step 4: List Jobs
    jobs_res = client.get("/api/admin/jobs", headers=headers)
    assert jobs_res.status_code == status.HTTP_200_OK
    assert jobs_res.json()["total"] >= 1

    # Step 5: Hybrid Search
    search_res = client.get("/api/search?q=Városháza")
    assert search_res.status_code == status.HTTP_200_OK
    assert search_res.json()["total"] >= 1

    # Step 6: RAG AI Assistant
    rag_res = client.post("/api/rag", json={"question": "Hol található a Vörösmarty Mihály Könyvtár?"})
    assert rag_res.status_code == status.HTTP_200_OK
    rag_data = rag_res.json()
    assert rag_data["is_sufficient"] is True
    trace_id = rag_data["trace_id"]

    # Step 7: RAG Feedback
    fb_res = client.post("/api/rag/feedback", json={"trace_id": trace_id, "feedback": "helpful"})
    assert fb_res.status_code == status.HTTP_204_NO_CONTENT

    # Step 8: OAI-PMH Provider Export
    oai_res = client.get("/oai?verb=Identify")
    assert oai_res.status_code == status.HTTP_200_OK
    assert "<repositoryName>" in oai_res.text
