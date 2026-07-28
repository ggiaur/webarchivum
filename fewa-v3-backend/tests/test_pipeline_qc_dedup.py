import uuid
import pytest
from spec.pipeline_schemas import QCInput, DedupCheckInput
from app.pipeline.qc_dedup import evaluate_quality_control, check_deduplication, calculate_hamming_distance


def test_calculate_hamming_distance():
    hex1 = "000000000000000f"
    hex2 = "0000000000000007"
    # 0x0f (1111) vs 0x07 (0111) -> 1 bit difference
    dist = calculate_hamming_distance(hex1, hex2)
    assert dist == 1


def test_evaluate_quality_control_good_text():
    snapshot_id = uuid.uuid4()
    inp = QCInput(
        snapshot_id=snapshot_id,
        raw_text="A" * 500,
        char_count=500,
        page_count=1,
        has_summary=True,
        chunk_count=2,
    )
    out = evaluate_quality_control(inp)
    assert out.score == 100
    assert out.auto_reject is False


def test_evaluate_quality_control_auto_reject():
    snapshot_id = uuid.uuid4()
    inp = QCInput(
        snapshot_id=snapshot_id,
        raw_text="Rövid",
        char_count=5,
        page_count=1,
        has_summary=False,
        chunk_count=0,
    )
    out = evaluate_quality_control(inp)
    assert out.score < 40
    assert out.auto_reject is True
    assert len(out.reasons) > 0


def test_check_deduplication_exact_and_near_match():
    snap1 = uuid.uuid4()
    snap2 = uuid.uuid4()

    existing_hashes = {"hash123": snap1}
    existing_simhashes = {"000000000000000f": snap2}

    # Exact match
    inp_exact = DedupCheckInput(
        content_hash="hash123",
        simhash="0000000000000000",
        simhash_threshold=3,
    )
    res_exact = check_deduplication(inp_exact, existing_hashes, existing_simhashes)
    assert res_exact.is_exact_duplicate is True
    assert res_exact.exact_match_snapshot_id == snap1

    # Near match (Hamming dist 1 <= threshold 3)
    inp_near = DedupCheckInput(
        content_hash="newhash999",
        simhash="0000000000000007",  # dist = 1
        simhash_threshold=3,
    )
    res_near = check_deduplication(inp_near, existing_hashes, existing_simhashes)
    assert res_near.is_exact_duplicate is False
    assert res_near.is_near_duplicate is True
    assert res_near.near_match_snapshot_id == snap2
    assert res_near.hamming_distance == 1
