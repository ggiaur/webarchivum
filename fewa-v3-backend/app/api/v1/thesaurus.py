import logging
from typing import Optional, List, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from app.api.deps import require_role
from app.crud import thesaurus as thesaurus_crud

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/thesaurus", tags=["Thesaurus"])


class SKOSConceptCreateSchema(BaseModel):
    pref_label_hu: str = Field(min_length=2, max_length=200)
    pref_label_en: Optional[str] = None
    alt_labels: Optional[List[str]] = None
    definition: Optional[str] = None
    scope_note: Optional[str] = None
    notation: Optional[str] = None
    broader_id: Optional[str] = None


class SKOSConceptUpdateSchema(BaseModel):
    pref_label_hu: Optional[str] = Field(None, min_length=2, max_length=200)
    pref_label_en: Optional[str] = None
    alt_labels: Optional[List[str]] = None
    definition: Optional[str] = None
    scope_note: Optional[str] = None
    notation: Optional[str] = None
    broader_id: Optional[str] = None
    is_deprecated: Optional[bool] = None


@router.get("", dependencies=[Depends(require_role("viewer"))])
def list_thesaurus(
    q: Optional[str] = Query(None, min_length=1),
    broader_id: Optional[str] = Query(None),
    include_deprecated: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    items, total = thesaurus_crud.list_concepts(
        q=q,
        broader_id=broader_id,
        include_deprecated=include_deprecated,
        page=page,
        page_size=page_size,
    )
    return {
        "items": items,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("", status_code=status.HTTP_201_CREATED, dependencies=[Depends(require_role("curator"))])
def create_thesaurus_concept(body: SKOSConceptCreateSchema):
    new_concept = thesaurus_crud.create_concept(body.model_dump())
    return new_concept


@router.patch("/{id}", dependencies=[Depends(require_role("curator"))])
def update_thesaurus_concept(id: str, body: SKOSConceptUpdateSchema):
    updates = body.model_dump(exclude_unset=True)
    updated = thesaurus_crud.update_concept(id, updates)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A tezaurusz fogalom nem található.",
        )
    return updated
