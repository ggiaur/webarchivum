import uuid
import pytest
from spec.pipeline_schemas import ChunkingInput
from app.pipeline.embedding import chunk_and_embed_text, generate_mock_embedding


def test_generate_mock_embedding_dim_768():
    vec = generate_mock_embedding("Fejér vármegyei webarchívum", dim=768)
    assert len(vec) == 768
    assert all(isinstance(x, float) for x in vec)


def test_chunk_and_embed_text_schema():
    snapshot_id = uuid.uuid4()
    text = (
        "Elindult a FEWA webarchívum projekt. "
        "A Vörösmarty Mihály Könyvtár gyűjteményi stratégiája alapján készül. "
        "PostgreSQL és pgvector adatbázist használ a hibrid kereséshez. "
        "A MinIO S3 objektumtároló biztosítja a WACZ fájlok biztonságos őrzését."
    )
    inp = ChunkingInput(
        snapshot_id=snapshot_id,
        raw_text=text,
        chunk_size=600,
        chunk_overlap=100,
    )

    out = chunk_and_embed_text(inp)

    assert out.snapshot_id == snapshot_id
    assert len(out.chunks) >= 1
    assert len(out.chunks[0].embedding) == 768
    assert out.embedding_model == "nomic-embed-text"
    assert out.embedding_version == "1.5"
    assert out.total_tokens > 0
