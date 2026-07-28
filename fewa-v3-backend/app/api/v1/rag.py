import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from app.services import rag_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/rag", tags=["Public"])


class RAGRequestSchema(BaseModel):
    question: str = Field(min_length=5, max_length=500)
    municipality_slug: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    top_k: int = Field(default=3, ge=1, le=10)


class RAGFeedbackSchema(BaseModel):
    trace_id: str
    feedback: str = Field(pattern="^(helpful|unhelpful|wrong)$")
    note: Optional[str] = Field(None, max_length=500)


@router.post("")
def rag_query(body: RAGRequestSchema):
    return rag_service.execute_rag_query(
        question=body.question,
        municipality_slug=body.municipality_slug,
        top_k=body.top_k,
    )


@router.post("/feedback", status_code=status.HTTP_204_NO_CONTENT)
def rag_feedback(body: RAGFeedbackSchema):
    success = rag_service.record_rag_feedback(
        trace_id=body.trace_id,
        feedback=body.feedback,
        note=body.note,
    )
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="A megadott trace_id nem található.",
        )
    return None
