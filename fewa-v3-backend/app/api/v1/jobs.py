import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from app.api.deps import require_role
from app.crud.sites import get_site_by_id
from app.workers.arq_worker import _JOBS_DB

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["Admin"])


class IngestRequestSchema(BaseModel):
    site_id: str
    policy_id: Optional[str] = None
    llm_profile_override: Optional[str] = None


class JobSchema(BaseModel):
    id: str
    job_type: str
    status: str
    snapshot_id: Optional[str] = None
    site_id: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    error_message: Optional[str] = None
    queued_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    duration_ms: Optional[int] = None


@router.post("/ingest", status_code=status.HTTP_202_ACCEPTED, dependencies=[Depends(require_role("archivist"))])
def trigger_ingest(body: IngestRequestSchema):
    site = get_site_by_id(body.site_id)
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A megadott site nem található.",
        )

    job_id = str(uuid.uuid4())
    snapshot_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    job_record = {
        "id": job_id,
        "job_type": "crawl",
        "status": "queued",
        "site_id": body.site_id,
        "snapshot_id": snapshot_id,
        "retry_count": 0,
        "max_retries": 3,
        "error_message": None,
        "queued_at": now_iso,
        "started_at": None,
        "completed_at": None,
        "duration_ms": None,
    }

    _JOBS_DB[job_id] = job_record
    return job_record


@router.get("/jobs", dependencies=[Depends(require_role("archivist"))])
def list_jobs(
    status: Optional[str] = Query(None),
    job_type: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    results = list(_JOBS_DB.values())

    if status:
        results = [j for j in results if j.get("status") == status]
    if job_type:
        results = [j for j in results if j.get("job_type") == job_type]

    total = len(results)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "items": results[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
