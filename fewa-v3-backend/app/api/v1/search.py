import logging
from typing import Optional
from fastapi import APIRouter, Query, status
from app.services.search_service import execute_hybrid_search

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Public"])


@router.get("/search")
def search_snapshots(
    q: str = Query(..., min_length=2, max_length=500),
    search_type: str = Query("hybrid", pattern="^(fulltext|vector|hybrid)$"),
    municipality_slug: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    return execute_hybrid_search(
        q=q,
        search_type=search_type,
        municipality_slug=municipality_slug,
        category=category,
        page=page,
        page_size=page_size,
    )
