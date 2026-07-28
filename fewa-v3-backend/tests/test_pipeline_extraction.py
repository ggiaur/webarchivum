import uuid
import pytest
from spec.pipeline_schemas import ExtractionInput
from app.pipeline.extraction import extract_text_from_wacz_stream, compute_content_hash, compute_simhash_hex


def test_compute_content_hash_deterministic():
    text1 = "  Fejér Vármegyei    Önkormányzat "
    text2 = "Fejér Vármegyei Önkormányzat"

    h1 = compute_content_hash(text1)
    h2 = compute_content_hash(text2)

    assert len(h1) == 64
    assert h1 == h2  # Whitespace normalized exact match


def test_compute_simhash_hex_length():
    text = "Székesfehérvár MJV Polgármesteri Hivatal közgyűlési határozatok felülvizsgálata."
    simhash = compute_simhash_hex(text)
    assert len(simhash) == 16


def test_extract_text_from_wacz_stream_schema():
    snapshot_id = uuid.uuid4()
    inp = ExtractionInput(
        snapshot_id=snapshot_id,
        wacz_minio_path="wacz/2026/07/test.wacz",
        language="hu",
    )
    html = "<html><body><h1>Székesfehérvári Hírek</h1><p>Megkezdődött a felújítás.</p></body></html>"

    out = extract_text_from_wacz_stream(inp, html)

    assert out.snapshot_id == snapshot_id
    assert "Székesfehérvári Hírek" in out.raw_text
    assert len(out.content_hash) == 64
    assert len(out.simhash) == 16
    assert out.extraction_method == "trafilatura"
