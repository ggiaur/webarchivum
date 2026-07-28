import uuid
import pytest
from spec.pipeline_schemas import NERInput
from app.pipeline.ner import extract_named_entities


def test_extract_named_entities_schema():
    snapshot_id = uuid.uuid4()
    text = (
        "Kovács János beszámolt a Székesfehérvár közgyűlési ülésen. "
        "A Vörösmarty Mihály Könyvtár és az OSZK megállapodást kötött."
    )
    inp = NERInput(
        snapshot_id=snapshot_id,
        raw_text=text,
        language="hu",
    )

    out = extract_named_entities(inp)

    assert out.snapshot_id == snapshot_id
    assert "Székesfehérvár" in out.locations
    assert "OSZK" in out.organizations or "VMK" in out.organizations
    assert out.model_version == "hu_core_news_lg-3.7.0"
    assert out.processing_time_ms >= 0
