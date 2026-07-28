from datetime import datetime, timezone
from typing import Optional
from spec.pipeline_schemas import QCInput, QCOutput, DedupCheckInput, DedupCheckOutput


def calculate_hamming_distance(hex1: str, hex2: str) -> int:
    """Calculates Hamming distance between two 16-character hex SimHash strings (64-bit)."""
    try:
        val1 = int(hex1, 16)
        val2 = int(hex2, 16)
        xor_val = val1 ^ val2
        return bin(xor_val).count("1")
    except Exception:
        return 64


def evaluate_quality_control(input_data: QCInput) -> QCOutput:
    """
    Evaluates quality score (0-100) based on text length, page count, summary, and chunk count.
    auto_reject = True if score < 40.
    """
    score = 100
    reasons = []

    if input_data.char_count < 100:
        score -= 50
        reasons.append("A szöveg túl rövid (< 100 karakter).")
    elif input_data.char_count < 300:
        score -= 20
        reasons.append("Kevés tartalom (< 300 karakter).")

    if not input_data.has_summary:
        score -= 15
        reasons.append("Hiányzó AI összefoglaló.")

    if input_data.chunk_count == 0:
        score -= 30
        reasons.append("Nincs érvényes szöveg-chunk.")

    score = max(0, min(100, score))
    auto_reject = score < 40

    return QCOutput(
        snapshot_id=input_data.snapshot_id,
        score=score,
        auto_reject=auto_reject,
        reasons=reasons,
        evaluated_at=datetime.now(timezone.utc),
    )


def check_deduplication(
    input_data: DedupCheckInput,
    existing_hashes: dict[str, str],   # content_hash -> snapshot_id
    existing_simhashes: dict[str, str], # simhash_hex -> snapshot_id
) -> DedupCheckOutput:
    """
    Checks exact duplicate (SHA-256) and near-duplicate (SimHash Hamming distance <= threshold).
    """
    exact_snapshot_id = existing_hashes.get(input_data.content_hash)
    if exact_snapshot_id:
        return DedupCheckOutput(
            is_exact_duplicate=True,
            exact_match_snapshot_id=exact_snapshot_id,
            is_near_duplicate=True,
            near_match_snapshot_id=exact_snapshot_id,
            hamming_distance=0,
        )

    # Check SimHash Hamming distance
    for simhash_hex, snapshot_id in existing_simhashes.items():
        dist = calculate_hamming_distance(input_data.simhash, simhash_hex)
        if dist <= input_data.simhash_threshold:
            return DedupCheckOutput(
                is_exact_duplicate=False,
                exact_match_snapshot_id=None,
                is_near_duplicate=True,
                near_match_snapshot_id=snapshot_id,
                hamming_distance=dist,
            )

    return DedupCheckOutput(
        is_exact_duplicate=False,
        exact_match_snapshot_id=None,
        is_near_duplicate=False,
        near_match_snapshot_id=None,
        hamming_distance=None,
    )
