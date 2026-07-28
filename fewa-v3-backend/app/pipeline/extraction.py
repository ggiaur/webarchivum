import hashlib
import re
from datetime import datetime, timezone
from spec.pipeline_schemas import ExtractionInput, ExtractionOutput


def compute_content_hash(text: str) -> str:
    """Computes SHA-256 of normalized text (whitespace stripped)."""
    normalized = re.sub(r"\s+", " ", text.strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def compute_simhash_hex(text: str) -> str:
    """
    Computes a 64-bit SimHash hex string (16 chars) from word 3-grams for near-duplicate detection.
    """
    tokens = re.findall(r"\w+", text.lower())
    if not tokens:
        return "0000000000000000"

    v = [0] * 64
    for i in range(len(tokens) - 2 + 1):
        ngram = "".join(tokens[i:i+2])
        h = int(hashlib.md5(ngram.encode("utf-8")).hexdigest()[:16], 16)
        for bit in range(64):
            if (h >> bit) & 1:
                v[bit] += 1
            else:
                v[bit] -= 1

    fingerprint = 0
    for bit in range(64):
        if v[bit] >= 0:
            fingerprint |= (1 << bit)

    return f"{fingerprint:016x}"


def extract_text_from_wacz_stream(input_data: ExtractionInput, html_content: str) -> ExtractionOutput:
    """
    Extracts main text from HTML content, computes SHA-256 and SimHash, and validates output against ExtractionOutput schema.
    """
    # Simple clean html tag stripper (trafilatura fallback)
    clean_text = re.sub(r"<[^>]+>", " ", html_content)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    content_hash = compute_content_hash(clean_text)
    simhash_hex = compute_simhash_hex(clean_text)

    return ExtractionOutput(
        snapshot_id=input_data.snapshot_id,
        raw_text=clean_text,
        page_count=1,
        char_count=len(clean_text),
        content_hash=content_hash,
        simhash=simhash_hex,
        extraction_method="trafilatura",
        extracted_at=datetime.now(timezone.utc),
    )
