"""Real admin API for the candidate discovery -> approval -> crawl -> QC
review workflow. Operates entirely on the real Postgres lifecycle state
machine via app/crud/archive.py and enqueues real arq jobs that
app/workers/arq_worker.py's WorkerSettings executes — no in-memory job
registry, no simulated qc_score.
"""

import uuid
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import urlparse

import asyncpg
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from jose import JWTError, jwt
from pydantic import BaseModel, HttpUrl

from app.api.deps import require_role
from app.core.arq_pool import get_arq_pool
from app.core.config import settings
from app.core.db import get_db_connection
from app.core.minio_client import minio_client
from app.api.v1.search import stream_wacz_response
from app.crud import archive
from app.services.search_service import get_document_by_id_for_curator

# Short enough to limit exposure if a URL leaks, long enough to replay a
# large archive without the token expiring mid-session.
WACZ_TOKEN_TTL_MINUTES = 60

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])


class IngestRequestSchema(BaseModel):
    seed_url: HttpUrl
    dc_title: Optional[str] = None
    depth: int = 2
    max_pages: int = 20


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
    try:
        candidate = await archive.create_candidate_snapshot(
            conn, site_id=str(site["id"]), seed_url=str(body.seed_url),
            dc_title=body.dc_title or domain,
            discovery_reason="Manual ingest via admin API",
            discovery_metadata={"source": "manual_ingest"},
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
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
            "depth": 2,
            "max_pages": 20,
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


@router.get("/documents/{doc_id}", dependencies=[Depends(require_role("curator"))])
async def get_document_for_review(doc_id: str, conn: asyncpg.Connection = Depends(get_db_connection)):
    """Admin-scoped document preview — unlike the public /api/documents/{id}
    (which only shows 'published' snapshots), this returns any snapshot
    with a recorded WACZ regardless of lifecycle_status, so a curator can
    actually replay/inspect content still awaiting a publish decision.
    See app/services/search_service.py::get_document_by_id_for_curator."""
    doc = await get_document_by_id_for_curator(conn, doc_id, minio_client)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A dokumentum nem található.")
    # Point replay at the curator WACZ route below, not the published-only
    # public one — a snapshot under review is by definition not published.
    if doc.get("wacz_url"):
        doc["wacz_url"] = f"/api/admin/wacz/{doc_id}?token={_wacz_access_token(doc_id)}"
    return doc


def _wacz_access_token(doc_id: str) -> str:
    """Short-lived token scoping WACZ access to one snapshot.

    ReplayWeb.page fetches the WACZ itself, from inside a Service Worker —
    it does not carry the dashboard's Authorization header, so a normal
    require_role dependency can't protect that fetch. A signed,
    snapshot-scoped, short-TTL query token keeps pre-publication content
    from being readable by anyone who merely guesses a UUID, without
    needing the header."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=WACZ_TOKEN_TTL_MINUTES)
    return jwt.encode(
        {"sub": str(doc_id), "type": "wacz", "exp": expire},
        settings.SECRET_KEY,
        algorithm="HS256",
    )


@router.get("/wacz/{doc_id}")
async def get_wacz_for_review(
    doc_id: str,
    token: str = Query(...),
    range: Optional[str] = Header(None),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Streams the WACZ of a snapshot that is not (yet) published, so a
    curator can actually replay what they're reviewing. Authorised by the
    scoped token from _wacz_access_token, not the Authorization header —
    see that function for why."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Érvénytelen vagy lejárt hozzáférési token.")
    if payload.get("type") != "wacz" or payload.get("sub") != str(doc_id):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "A token nem ehhez a dokumentumhoz tartozik.")

    try:
        row = await conn.fetchrow("SELECT wacz_minio_path FROM archived_snapshots WHERE id = $1", doc_id)
    except (ValueError, asyncpg.DataError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A dokumentum nem található.")
    if row is None or not row["wacz_minio_path"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Az archív állomány nem található.")

    return stream_wacz_response(row["wacz_minio_path"], range)
