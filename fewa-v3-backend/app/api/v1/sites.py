import logging
from typing import Optional, List, Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, HttpUrl
from app.api.deps import require_role
from app.crud import sites as sites_crud

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin/sites", tags=["Admin"])


class SiteCreateSchema(BaseModel):
    domain: str
    base_url: str
    display_name: Optional[str] = None
    priority: str = "medium"
    category: str = "egyéb"
    crawl_frequency: str = "monthly"
    municipality_id: Optional[str] = None
    curator_notes: Optional[str] = None
    oszk_status: str = "unknown"
    robots_txt_respect: bool = True
    requires_js: bool = False


class SiteUpdateSchema(BaseModel):
    display_name: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    crawl_frequency: Optional[str] = None
    municipality_id: Optional[str] = None
    curator_notes: Optional[str] = None
    oszk_status: Optional[str] = None
    is_active_collection: Optional[bool] = None
    robots_txt_respect: Optional[bool] = None
    requires_js: Optional[bool] = None


@router.get("", dependencies=[Depends(require_role("archivist"))])
def list_sites(
    priority: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    is_active_collection: Optional[bool] = Query(None),
    municipality_slug: Optional[str] = Query(None),
    oszk_status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = sites_crud.list_sites(
        priority=priority,
        category=category,
        is_active_collection=is_active_collection,
        municipality_slug=municipality_slug,
        oszk_status=oszk_status,
        page=page,
        page_size=page_size,
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_role("archivist"))])
def create_site(body: SiteCreateSchema):
    try:
        new_site = sites_crud.create_site(body.model_dump())
        return new_site
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.get("/{id}", dependencies=[Depends(require_role("archivist"))])
def get_site(id: str):
    site = sites_crud.get_site_by_id(id)
    if not site:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A site nem található.",
        )
    return site


@router.patch("/{id}", dependencies=[Depends(require_role("archivist"))])
def update_site(id: str, body: SiteUpdateSchema):
    updates = body.model_dump(exclude_unset=True)
    updated = sites_crud.update_site(id, updates)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A site nem található.",
        )
    return updated
