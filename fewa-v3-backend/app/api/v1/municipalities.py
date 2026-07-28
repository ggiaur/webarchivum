import logging
from typing import List, Optional
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/municipalities", tags=["Reference"])


class MunicipalitySchema(BaseModel):
    id: str
    name: str
    slug: str
    county: str = "Fejér"
    is_active: bool = True
    sort_order: int = 100


# Initial seed list of Fejér county municipalities (for reference & testing)
FEJER_MUNICIPALITIES_SEED = [
    MunicipalitySchema(
        id="muni-001-szekesfehervar",
        name="Székesfehérvár",
        slug="szekesfehervar",
        county="Fejér",
        is_active=True,
        sort_order=10,
    ),
    MunicipalitySchema(
        id="muni-002-dunauvaros",
        name="Dunaújváros",
        slug="dunauvaros",
        county="Fejér",
        is_active=True,
        sort_order=20,
    ),
    MunicipalitySchema(
        id="muni-003-mor",
        name="Mór",
        slug="mor",
        county="Fejér",
        is_active=True,
        sort_order=30,
    ),
    MunicipalitySchema(
        id="muni-004-bicske",
        name="Bicske",
        slug="bicske",
        county="Fejér",
        is_active=True,
        sort_order=40,
    ),
    MunicipalitySchema(
        id="muni-005-sarbogard",
        name="Sárbogárd",
        slug="sarbogard",
        county="Fejér",
        is_active=True,
        sort_order=50,
    ),
    MunicipalitySchema(
        id="muni-006-gárdony",
        name="Gárdony",
        slug="gardony",
        county="Fejér",
        is_active=True,
        sort_order=60,
    ),
    MunicipalitySchema(
        id="muni-007-enying",
        name="Enying",
        slug="enying",
        county="Fejér",
        is_active=True,
        sort_order=70,
    ),
    MunicipalitySchema(
        id="muni-008-martonvasar",
        name="Martonvásár",
        slug="martonvasar",
        county="Fejér",
        is_active=True,
        sort_order=80,
    ),
    MunicipalitySchema(
        id="muni-009-velence",
        name="Velence",
        slug="velence",
        county="Fejér",
        is_active=True,
        sort_order=90,
    ),
    MunicipalitySchema(
        id="muni-010-szabadbattyan",
        name="Szabadbattyán",
        slug="szabadbattyan",
        county="Fejér",
        is_active=False,  # Inactive test entry
        sort_order=999,
    ),
]


@router.get("", response_model=List[MunicipalitySchema])
def list_municipalities(include_inactive: bool = False):
    """Returns active municipalities sorted by sort_order."""
    result = [m for m in FEJER_MUNICIPALITIES_SEED if m.is_active or include_inactive]
    result.sort(key=lambda x: x.sort_order)
    return result
