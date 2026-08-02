"""Real integration tests for the RAG query/feedback API - against the same
isolated test Postgres as the other DB-backed test modules. Replaces the
previous version, which asserted against a pure in-memory dict
(_AI_TRACES_DB, reset on every process restart) - found while auditing the
codebase for the same in-memory-storage bug class already fixed for
users/thesaurus/sites, and missed for this module.

Note: execute_rag_query() itself is still a hardcoded keyword-match
simulation, not real AI (a known, separately-tracked limitation requiring
an LLM/embedding infrastructure decision - not touched here). This fix is
scoped to just the trace/feedback persistence, so feedback submitted on a
(fake) AI answer survives a server restart instead of silently 404ing."""

import os

import asyncpg
import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient

from app.api.v1.rag import router as rag_router
from app.core.db import get_db_connection

TEST_DSN = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql://fewa_admin:fewa_dev_local_only@localhost:5460/fewa_v3",
)


async def _override_get_db_connection():
    connection = await asyncpg.connect(dsn=TEST_DSN)
    try:
        yield connection
    finally:
        await connection.close()


app = FastAPI()
app.include_router(rag_router)
app.dependency_overrides[get_db_connection] = _override_get_db_connection

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clean_ai_traces():
    import asyncio

    async def _truncate():
        conn = await asyncpg.connect(dsn=TEST_DSN)
        try:
            await conn.execute("DELETE FROM ai_traces")
        finally:
            await conn.close()

    asyncio.run(_truncate())
    yield


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


def test_rag_query_persists_trace_to_postgres():
    """The core regression this test module exists for: a trace row must
    actually land in ai_traces, not just an in-memory dict."""
    response = client.post(
        "/api/rag",
        json={"question": "Hol található a Vörösmarty Mihály Könyvtár?"},
    )
    trace_id = response.json()["trace_id"]

    import asyncio

    async def _fetch():
        conn = await asyncpg.connect(dsn=TEST_DSN)
        try:
            return await conn.fetchrow("SELECT * FROM ai_traces WHERE id = $1", trace_id)
        finally:
            await conn.close()

    row = asyncio.run(_fetch())
    assert row is not None
    assert row["trace_type"] == "rag_query"
    assert row["prompt_text"] == "Hol található a Vörösmarty Mihály Könyvtár?"
    assert float(row["confidence_score"]) >= 0.6


def test_rag_feedback_success():
    query_res = client.post(
        "/api/rag",
        json={"question": "Hol található a Vörösmarty Mihály Könyvtár?"},
    )
    trace_id = query_res.json()["trace_id"]

    fb_res = client.post(
        "/api/rag/feedback",
        json={"trace_id": trace_id, "feedback": "helpful", "note": "Pontos válasz"},
    )
    assert fb_res.status_code == status.HTTP_204_NO_CONTENT


def test_rag_feedback_survives_across_requests():
    """Regression: with the old in-memory dict, a fresh process (or - in
    practice - a redeployed/restarted backend between the query and the
    feedback call) would 404 here even for a trace_id that really was
    returned by a real prior query. Simulate that by fetching the trace back
    from Postgres directly (a separate connection/"process") rather than
    relying on in-process state."""
    query_res = client.post(
        "/api/rag",
        json={"question": "Hol található a Vörösmarty Mihály Könyvtár?"},
    )
    trace_id = query_res.json()["trace_id"]

    import asyncio

    async def _feedback_already_persisted():
        conn = await asyncpg.connect(dsn=TEST_DSN)
        try:
            return await conn.fetchval(
                "SELECT user_feedback FROM ai_traces WHERE id = $1", trace_id
            )
        finally:
            await conn.close()

    assert asyncio.run(_feedback_already_persisted()) is None

    fb_res = client.post(
        "/api/rag/feedback",
        json={"trace_id": trace_id, "feedback": "wrong", "note": "Rossz forrás"},
    )
    assert fb_res.status_code == status.HTTP_204_NO_CONTENT

    async def _feedback_persisted():
        conn = await asyncpg.connect(dsn=TEST_DSN)
        try:
            return await conn.fetchrow(
                "SELECT user_feedback, feedback_note FROM ai_traces WHERE id = $1", trace_id
            )
        finally:
            await conn.close()

    row = asyncio.run(_feedback_persisted())
    assert row["user_feedback"] == "wrong"
    assert row["feedback_note"] == "Rossz forrás"


def test_rag_feedback_unknown_trace_id_returns_404():
    fb_res = client.post(
        "/api/rag/feedback",
        json={"trace_id": "00000000-0000-0000-0000-000000000000", "feedback": "helpful"},
    )
    assert fb_res.status_code == status.HTTP_404_NOT_FOUND
