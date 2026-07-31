"""Real admin API for the candidate discovery -> approval -> crawl -> QC
review workflow. Operates entirely on the real Postgres lifecycle state
machine via app/crud/archive.py and enqueues real arq jobs that
app/workers/arq_worker.py's WorkerSettings executes — no in-memory job
registry, no simulated qc_score.
"""

import uuid
import logging
from typing import Optional
from urllib.parse import urlparse

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, HttpUrl

from app.api.deps import require_role
from app.core.arq_pool import get_arq_pool
from app.core.config import settings
from app.core.db import get_db_connection
from app.crud import archive

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])


class IngestRequestSchema(BaseModel):
    seed_url: HttpUrl
    dc_title: Optional[str] = None
    depth: int = 3
    max_pages: int = 100


class CandidateDecisionSchema(BaseModel):
    reason: str


class QualityReviewDecisionSchema(BaseModel):
    accept: bool
    reason: str


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_role("curator"))])
async def trigger_ingest(
    body: IngestRequestSchema,
    conn: asyncpg.Connection = Depends(get_db_connection),
    arq_pool=Depends(get_arq_pool),
):
    """Admin-triggered ingest of a specific seed URL: resolves/creates the
    real site row, creates a candidate snapshot, auto-approves it (the
    admin's explicit action IS the approval — matches the discovery-queue
    flow where a curator approves an already-flagged candidate), and
    enqueues a real crawl job."""
    domain = urlparse(str(body.seed_url)).netloc
    if not domain:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Érvénytelen seed_url: nem sikerült domaint kinyerni.")

    site = await archive.get_or_create_site_by_domain(
        conn, domain=domain, base_url=str(body.seed_url), display_name=body.dc_title,
    )
    candidate = await archive.create_candidate_snapshot(
        conn, site_id=str(site["id"]), seed_url=str(body.seed_url),
        dc_title=body.dc_title or domain,
        discovery_reason="Manual ingest via admin API",
        discovery_metadata={"source": "manual_ingest"},
    )
    approved = await archive.approve_candidate(conn, candidate["id"], user_id=None, reason="Manual ingest: admin-approved on submission")

    job_id = uuid.uuid4()
    await arq_pool.enqueue_job(
        "run_crawl_job",
        {
            "job_id": str(job_id),
            "site_id": str(site["id"]),
            "snapshot_id": str(candidate["id"]),
            "seed_url": str(body.seed_url),
            "depth": body.depth,
            "max_pages": body.max_pages,
        },
        _job_id=str(job_id),
    )

    return {
        "job_id": str(job_id),
        "snapshot_id": str(candidate["id"]),
        "site_id": str(site["id"]),
        "lifecycle_status": approved["lifecycle_status"],
    }


@router.get("/candidates", dependencies=[Depends(require_role("curator"))])
async def list_candidates(conn: asyncpg.Connection = Depends(get_db_connection)):
    """Discovery candidates awaiting curator approve/reject decision."""
    rows = await archive.list_candidate_queue(conn)
    return {"items": rows, "total": len(rows)}


@router.post("/candidates/{snapshot_id}/approve", dependencies=[Depends(require_role("curator"))])
async def approve_candidate_endpoint(
    snapshot_id: uuid.UUID,
    body: CandidateDecisionSchema,
    conn: asyncpg.Connection = Depends(get_db_connection),
    arq_pool=Depends(get_arq_pool),
):
    try:
        result = await archive.approve_candidate(conn, str(snapshot_id), user_id=None, reason=body.reason)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))

    job_id = uuid.uuid4()
    row = await conn.fetchrow("SELECT seed_url, site_id FROM archived_snapshots WHERE id = $1", snapshot_id)
    await arq_pool.enqueue_job(
        "run_crawl_job",
        {
            "job_id": str(job_id),
            "site_id": str(row["site_id"]),
            "snapshot_id": str(snapshot_id),
            "seed_url": row["seed_url"],
            "depth": 3,
            "max_pages": 100,
        },
        _job_id=str(job_id),
    )
    return {**result, "job_id": str(job_id)}


@router.post("/candidates/{snapshot_id}/reject", dependencies=[Depends(require_role("curator"))])
async def reject_candidate_endpoint(
    snapshot_id: uuid.UUID,
    body: CandidateDecisionSchema,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    try:
        return await archive.reject_candidate(conn, str(snapshot_id), reason=body.reason)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))


@router.get("/quality-review", dependencies=[Depends(require_role("curator"))])
async def list_quality_review(conn: asyncpg.Connection = Depends(get_db_connection)):
    """Archived snapshots at/below QUALITY_AUTO_ACCEPT_THRESHOLD (or not yet
    QC'd) awaiting a human accept/reject decision — see
    app/crud/archive.py::record_qc_result for the auto-accept logic."""
    rows = await archive.list_quality_review_queue(conn, threshold=settings.QUALITY_AUTO_ACCEPT_THRESHOLD)
    return {"items": rows, "total": len(rows), "threshold": settings.QUALITY_AUTO_ACCEPT_THRESHOLD}


@router.post("/quality-review/{snapshot_id}/decide", dependencies=[Depends(require_role("curator"))])
async def decide_quality_review_endpoint(
    snapshot_id: uuid.UUID,
    body: QualityReviewDecisionSchema,
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    try:
        return await archive.decide_quality_review(
            conn, str(snapshot_id), accept=body.accept, user_id=None, reason=body.reason,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
