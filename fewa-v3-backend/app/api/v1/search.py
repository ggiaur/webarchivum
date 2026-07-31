import logging
from typing import Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.db import get_db_connection
from app.core.minio_client import minio_client
from app.services.search_service import execute_hybrid_search, get_document_by_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Public"])


@router.get("/search")
async def search_snapshots(
    q: Optional[str] = Query(None, max_length=500),
    search_type: str = Query("hybrid", pattern="^(fulltext|vector|hybrid)$"),
    municipality_slug: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    return await execute_hybrid_search(
        conn,
        q=q,
        search_type=search_type,
        municipality_slug=municipality_slug,
        category=category,
        page=page,
        page_size=page_size,
    )


@router.get("/documents/{doc_id}")
async def get_document(doc_id: str, conn: asyncpg.Connection = Depends(get_db_connection)):
    """Public detail view — includes wacz_url, a presigned MinIO URL for
    ReplayWeb.page (see fewa-v3-frontend's document page) to load the real
    archived WACZ directly. Only 'published' snapshots are visible; anything
    else is a real 404, not a fabricated placeholder."""
    doc = await get_document_by_id(conn, doc_id, minio_client)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A dokumentum nem található vagy még nem publikus.")
    return doc
