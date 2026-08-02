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


@router.get("/stats")
async def public_stats(conn: asyncpg.Connection = Depends(get_db_connection)):
    """Real counts for the public footer's status widget — this used to be
    a hardcoded "Mind a 87 gyűjteményi webhely..." string with an invented
    number, unrelated to actual DB state."""
    row = await conn.fetchrow(
        """
        SELECT
            (SELECT COUNT(*) FROM sites WHERE is_active_collection = TRUE) AS active_sites,
            (SELECT COUNT(*) FROM archived_snapshots WHERE lifecycle_status = 'published') AS published_documents
        """
    )
    return {"active_sites": row["active_sites"], "published_documents": row["published_documents"]}


CATEGORY_META_HU = {
    "kozintézmény": ("🏛️", "Önkormányzatok & Hivatalok"),
    "civil": ("🤝", "Civil Szervezetek"),
    "média": ("📰", "Helyi Sajtó & Média"),
    "vállalkozás": ("🏢", "Vállalkozások"),
    "kulturális": ("📚", "Kulturális & Könyvtári Örökség"),
    "egyéb": ("📁", "Egyéb"),
}


@router.get("/collections")
async def public_collections(conn: asyncpg.Connection = Depends(get_db_connection)):
    """Real per-category counts from published snapshots — the frontend's
    /collections page previously had zero backend behind it at all: a
    hardcoded array of 3 categories with fabricated counts (42/18/27),
    unrelated to site_category_enum's real 6 values or actual DB state.
    Same public-facing-fake-data bug class as the old search_service.py
    (see that module's docstring — the highest-severity finding of this
    session)."""
    rows = await conn.fetch(
        "SELECT site_category, COUNT(*) AS count FROM v_published_snapshots "
        "GROUP BY site_category ORDER BY count DESC"
    )
    return {
        "collections": [
            {
                "id": row["site_category"],
                "icon": CATEGORY_META_HU.get(row["site_category"], ("📁", row["site_category"]))[0],
                "name": CATEGORY_META_HU.get(row["site_category"], ("📁", row["site_category"]))[1],
                "count": row["count"],
            }
            for row in rows
        ]
    }


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
