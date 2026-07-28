import logging
from typing import Optional
from fastapi import APIRouter, Query, Response, status
from app.services import oaipmh_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["OAI-PMH"])


@router.get("/oai")
def oai_pmh_provider(
    verb: str = Query(..., description="OAI verb: Identify, ListSets, ListMetadataFormats, ListIdentifiers, ListRecords, GetRecord"),
    metadataPrefix: Optional[str] = Query("oai_dc"),
    identifier: Optional[str] = Query(None),
    set: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None, alias="from"),
    until: Optional[str] = Query(None),
    resumptionToken: Optional[str] = Query(None),
):
    xml_content = oaipmh_service.generate_oaipmh_xml(
        verb=verb,
        metadata_prefix=metadataPrefix,
        identifier=identifier,
        resumption_token=resumptionToken,
    )
    return Response(content=xml_content, media_type="application/xml")
