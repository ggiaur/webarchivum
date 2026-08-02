import logging
from typing import Optional
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from app.services import rag_service
from app.core.db import get_db_connection

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
async def rag_query(body: RAGRequestSchema, conn: asyncpg.Connection = Depends(get_db_connection)):
    return await rag_service.execute_rag_query(
        conn,
        question=body.question,
        municipality_slug=body.municipality_slug,
        top_k=body.top_k,
    )


@router.post("/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def rag_feedback(body: RAGFeedbackSchema, conn: asyncpg.Connection = Depends(get_db_connection)):
    success = await rag_service.record_rag_feedback(
        conn,
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
