"""FEWA catalogue contract: list ids, then resolve every detail original URL."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from fewa_adapter import DETAIL_ENDPOINT, LIST_ENDPOINT, ORIGINAL_URL_FIELD, FewaCatalogueAdapter


class FixtureTransport:
    def __init__(self):
        self.calls = []
        self.rows = [{"id": item, "standard_fewa_id": f"FEWA-{item}", "uniform_title": f"Title {item}"}
                     for item in range(1, 325)]

    def post_json(self, endpoint, payload):
        self.calls.append((endpoint, payload))
        if endpoint == LIST_ENDPOINT:
            assert payload == {"category": "s_all", "autocomplete": ""}
            return self.rows
        assert endpoint == DETAIL_ENDPOINT
        record_id = payload["id"]
        return [{ORIGINAL_URL_FIELD: f"https://source-{record_id}.example.org/"}]


def test_fewa_list_324_rows_resolve_to_324_external_detail_original_urls():
    transport = FixtureTransport()
    resolutions = FewaCatalogueAdapter(transport, retrieved_at="2026-08-13T00:00:00Z").enumerate_resolutions()
    assert len(resolutions) == 324
    assert len([call for call in transport.calls if call[0] == DETAIL_ENDPOINT]) == 324
    assert all(item.state == "resolved" and item.record is not None for item in resolutions)
    assert len({item.record.source_url for item in resolutions if item.record}) == 324
    record = resolutions[0].record
    assert record is not None
    evidence = dict(record.provenance)
    assert evidence["detail_endpoint"] == DETAIL_ENDPOINT
    assert evidence["original_url_field"] == ORIGINAL_URL_FIELD
    assert "source-1.example.org" in evidence["detail_response"]


def test_fewa_detail_missing_malformed_or_portal_url_is_review_not_candidate():
    class BadTransport(FixtureTransport):
        def __init__(self, original):
            super().__init__()
            self.rows = [{"id": 1, "uniform_title": "bad"}]
            self.original = original

        def post_json(self, endpoint, payload):
            if endpoint == LIST_ENDPOINT:
                return self.rows
            return [{}] if self.original is None else [{ORIGINAL_URL_FIELD: self.original}]

    for value in (None, "mailto:editor@example.org", "https://fewa.vmk.hu/"):
        result = FewaCatalogueAdapter(BadTransport(value), retrieved_at="now").enumerate_resolutions()[0]
        assert result.state == "review_required"
        assert result.record is None
