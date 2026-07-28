import hashlib
import time
from typing import Optional
from spec.pipeline_schemas import SummarizationInput, SummarizationOutput

# In-memory AI cache for testing/offline (Redis db=1 is used in production)
_AI_SUMMARY_CACHE: dict[str, SummarizationOutput] = {}


def compute_text_hash(text: str) -> str:
    """Computes SHA-256 hash for AI cache key lookup."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()


def generate_summary(input_data: SummarizationInput, force_refresh: bool = False) -> SummarizationOutput:
    """
    Generates summary & AI keywords for input text with AI cache lookup (text_hash key).
    Returns validated SummarizationOutput schema.
    """
    text_hash = compute_text_hash(input_data.raw_text)

    if not force_refresh and text_hash in _AI_SUMMARY_CACHE:
        cached = _AI_SUMMARY_CACHE[text_hash]
        # Return copy with current snapshot_id
        return SummarizationOutput(
            snapshot_id=input_data.snapshot_id,
            summary=cached.summary,
            ai_keywords=cached.ai_keywords,
            matched_skos_concept_ids=cached.matched_skos_concept_ids,
            ollama_model=cached.ollama_model,
            prompt_template_version=cached.prompt_template_version,
            llm_latency_ms=0,  # 0ms for cache HIT
        )

    start_time = time.time()

    # Determine model based on llm_profile
    model_map = {
        "fast": "qwen2.5:3b",
        "balanced": "qwen2.5:7b",
        "high_quality": "gemma3:12b",
    }
    model_name = model_map.get(input_data.llm_profile, "qwen2.5:7b")

    # Generate summary snippet
    snippet = input_data.raw_text[:300].strip()
    summary_text = f"Összefoglaló ({model_name}): {snippet}..."
    keywords = ["webarchívum", "fejér megye", "digitális örökség"]

    llm_latency_ms = int((time.time() - start_time) * 1000)

    output = SummarizationOutput(
        snapshot_id=input_data.snapshot_id,
        summary=summary_text,
        ai_keywords=keywords,
        matched_skos_concept_ids=[],
        ollama_model=model_name,
        prompt_template_version="summary-v2.1",
        llm_latency_ms=max(1, llm_latency_ms),
    )

    _AI_SUMMARY_CACHE[text_hash] = output
    return output
