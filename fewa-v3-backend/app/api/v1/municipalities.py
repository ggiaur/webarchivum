import logging
from typing import List

import asyncpg
from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.db import get_db_connection

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/municipalities", tags=["Reference"])


class MunicipalitySchema(BaseModel):
    id: str
    name: str
    slug: str
    county: str = "Fejér"
    is_active: bool = True
    sort_order: int = 100


@router.get("", response_model=List[MunicipalitySchema])
async def list_municipalities(include_inactive: bool = False, conn: asyncpg.Connection = Depends(get_db_connection)):
    """Real Fejér vármegye municipalities from the municipalities table
    (see spec/migrations/003_seed_fejer_municipalities.sql — this used to
    be a hardcoded in-memory list with fabricated non-UUID ids, never
    backed by the DB at all)."""
    where = "" if include_inactive else "WHERE is_active = TRUE"
    rows = await conn.fetch(
        f"SELECT id, name, slug, county, is_active, sort_order FROM municipalities {where} ORDER BY sort_order"
    )
    return [
        MunicipalitySchema(id=str(r["id"]), name=r["name"], slug=r["slug"], county=r["county"],
                            is_active=r["is_active"], sort_order=r["sort_order"])
        for r in rows
    ]
