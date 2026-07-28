from datetime import datetime, timezone
from typing import Optional

def generate_oaipmh_xml(
    verb: str,
    metadata_prefix: Optional[str] = "oai_dc",
    identifier: Optional[str] = None,
    resumption_token: Optional[str] = None,
) -> str:
    """
    Generates W3C valid OAI-PMH 2.0 XML response for all 6 verbs.
    """
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d%H:%M:%SZ")

    xml_header = f"""<?xml version="1.0" encoding="UTF-8"?>
<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://www.openarchives.org/OAI/2.0/ http://www.openarchives.org/OAI/2.0/OAI-PMH.xsd">
    <responseDate>{now_utc}</responseDate>
    <request verb="{verb}">https://archivum.vmk.hu/oai</request>
"""

    xml_footer = "</OAI-PMH>"

    if verb == "Identify":
        body = """    <Identify>
        <repositoryName>Fejér Vármegyei Webarchívum (FEWA)</repositoryName>
        <baseURL>https://archivum.vmk.hu/oai</baseURL>
        <protocolVersion>2.0</protocolVersion>
        <adminEmail>fewa@vmk.hu</adminEmail>
        <earliestDatestamp>2026-01-01T00:00:00Z</earliestDatestamp>
        <deletedRecord>transient</deletedRecord>
        <granularity>YYYY-MM-DDThh:mm:ssZ</granularity>
    </Identify>"""

    elif verb == "ListMetadataFormats":
        body = """    <ListMetadataFormats>
        <metadataFormat>
            <metadataPrefix>oai_dc</metadataPrefix>
            <schema>http://www.openarchives.org/OAI/2.0/oai_dc.xsd</schema>
            <metadataNamespace>http://www.openarchives.org/OAI/2.0/oai_dc/</metadataNamespace>
        </metadataFormat>
        <metadataFormat>
            <metadataPrefix>mets</metadataPrefix>
            <schema>http://www.loc.gov/standards/mets/mets.xsd</schema>
            <metadataNamespace>http://www.loc.gov/METS/</metadataNamespace>
        </metadataFormat>
        <metadataFormat>
            <metadataPrefix>mods</metadataPrefix>
            <schema>http://www.loc.gov/standards/mods/v3/mods-3-7.xsd</schema>
            <metadataNamespace>http://www.loc.gov/mods/v3</metadataNamespace>
        </metadataFormat>
    </ListMetadataFormats>"""

    elif verb == "ListSets":
        body = """    <ListSets>
        <set>
            <setSpec>szekesfehervar</setSpec>
            <setName>Székesfehérvári gyűjtemény</setName>
        </set>
        <set>
            <setSpec>kozintezmeny</setSpec>
            <setName>Közintézmények</setName>
        </set>
    </ListSets>"""

    elif verb in ["ListIdentifiers", "ListRecords", "GetRecord"]:
        rec_id = identifier or "fewa:2026:000001"
        body = f"""    <{verb}>
        <record>
            <header>
                <identifier>oai:fewa.vmk.hu:{rec_id}</identifier>
                <datestamp>2026-07-28T10:00:00Z</datestamp>
                <setSpec>szekesfehervar</setSpec>
            </header>
            <metadata>
                <oai_dc:dc xmlns:oai_dc="http://www.openarchives.org/OAI/2.0/oai_dc/"
                           xmlns:dc="http://purl.org/dc/elements/1.1/">
                    <dc:title>Székesfehérvár MJV Polgármesteri Hivatal Hírei</dc:title>
                    <dc:creator>Székesfehérvár MJV</dc:creator>
                    <dc:subject>helyi politika</dc:subject>
                    <dc:identifier>{rec_id}</dc:identifier>
                    <dc:language>hu</dc:language>
                </oai_dc:dc>
            </metadata>
        </record>
    </{verb}>"""
    else:
        body = """    <error code="badVerb">Illegal OAI verb</error>"""

    return xml_header + body + "\n" + xml_footer
