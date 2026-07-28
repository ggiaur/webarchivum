import pytest
from fastapi import FastAPI, status
from fastapi.testclient import TestClient
from app.api.v1.oaipmh import router as oaipmh_router

app = FastAPI()
app.include_router(oaipmh_router)

client = TestClient(app)


def test_oai_identify_verb_returns_xml():
    response = client.get("/oai?verb=Identify")
    assert response.status_code == status.HTTP_200_OK
    assert "application/xml" in response.headers["content-type"]
    assert "<Identify>" in response.text
    assert "<repositoryName>Fejér Vármegyei Webarchívum (FEWA)</repositoryName>" in response.text


def test_oai_list_metadata_formats_verb():
    response = client.get("/oai?verb=ListMetadataFormats")
    assert response.status_code == status.HTTP_200_OK
    assert "<metadataPrefix>oai_dc</metadataPrefix>" in response.text
    assert "<metadataPrefix>mets</metadataPrefix>" in response.text


def test_oai_list_records_verb():
    response = client.get("/oai?verb=ListRecords&metadataPrefix=oai_dc")
    assert response.status_code == status.HTTP_200_OK
    assert "<ListRecords>" in response.text
    assert "<dc:title>" in response.text
