import uuid
import pytest
from spec.pipeline_schemas import SummarizationInput
from app.pipeline.summarization import generate_summary, compute_text_hash


def test_summarization_and_ai_cache_hit():
    snapshot_id_1 = uuid.uuid4()
    snapshot_id_2 = uuid.uuid4()
    text = "A Vörösmarty Mihály Könyvtár digitális örökség megőrzési projektje Fejér vármegyében."

    inp1 = SummarizationInput(
        snapshot_id=snapshot_id_1,
        raw_text=text,
        llm_profile="balanced",
    )

    # First run (Cache MISS)
    out1 = generate_summary(inp1)
    assert out1.snapshot_id == snapshot_id_1
    assert out1.ollama_model == "qwen2.5:7b"
    assert out1.prompt_template_version == "summary-v2.1"
    assert len(out1.summary) > 0

    # Second run with same text (Cache HIT -> 0ms latency)
    inp2 = SummarizationInput(
        snapshot_id=snapshot_id_2,
        raw_text=text,
        llm_profile="balanced",
    )
    out2 = generate_summary(inp2)
    assert out2.snapshot_id == snapshot_id_2
    assert out2.summary == out1.summary
    assert out2.llm_latency_ms == 0  # 0ms for Cache HIT
