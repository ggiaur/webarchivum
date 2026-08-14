import logging
from typing import Optional

import asyncpg
from botocore.exceptions import ClientError
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse

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
    """Public detail view — includes wacz_url, a same-origin path served by
    the /api/wacz/{id} route below, for ReplayWeb.page (see
    fewa-v3-frontend's document page) to load the real archived WACZ. Only
    'published' snapshots are visible; anything else is a real 404, not a
    fabricated placeholder."""
    doc = await get_document_by_id(conn, doc_id, minio_client)
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A dokumentum nem található vagy még nem publikus.")
    return doc


def stream_wacz_response(wacz_minio_path: str, range_header: Optional[str]):
    """Shared by the public and curator WACZ routes: streams the object out
    of MinIO, forwarding any Range request and mirroring MinIO's own
    ContentRange/ContentLength back so ReplayWeb.page can read the archive
    as a remote zip. See app/core/minio_client.py::get_wacz_object for why
    Range support is mandatory here."""
    try:
        obj = minio_client.get_wacz_object(wacz_minio_path, range_header)
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code")
        if code in ("NoSuchKey", "404", "InvalidRange"):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Az archív állomány nem található.")
        logger.exception("MinIO read failed for %s", wacz_minio_path)
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, "Az archív tároló jelenleg nem elérhető.")

    body = obj["Body"]
    headers = {"Accept-Ranges": "bytes"}
    if obj.get("ContentRange"):
        headers["Content-Range"] = obj["ContentRange"]
    if obj.get("ContentLength") is not None:
        headers["Content-Length"] = str(obj["ContentLength"])

    return StreamingResponse(
        body.iter_chunks(chunk_size=64 * 1024),
        status_code=status.HTTP_206_PARTIAL_CONTENT if range_header and obj.get("ContentRange")
        else status.HTTP_200_OK,
        media_type="application/wacz",
        headers=headers,
    )


@router.get("/wacz/{doc_id}")
async def get_wacz(
    doc_id: str,
    range: Optional[str] = Header(None),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Streams a published snapshot's WACZ from the same origin as the page.

    Replaces handing the browser a presigned MinIO URL: those pointed at
    MINIO_ENDPOINT (e.g. localhost:9002), which is unreachable from a real
    user's browser and mixed content on an https:// page — replay failed
    with "TypeError: Failed to fetch" (2026-08-02). Published-only, matching
    the public /api/documents/{id} gate; the curator equivalent for
    pre-publication review lives in app/api/v1/jobs.py."""
    try:
        row = await conn.fetchrow(
            "SELECT wacz_minio_path FROM archived_snapshots WHERE id = $1 AND lifecycle_status = 'published'",
            doc_id,
        )
    except (ValueError, asyncpg.DataError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A dokumentum nem található vagy még nem publikus.")

    if row is None or not row["wacz_minio_path"]:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "A dokumentum nem található vagy még nem publikus.")

    return stream_wacz_response(row["wacz_minio_path"], range)
