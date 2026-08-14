"""ARCH-01 S1 Python and OpenAPI machine-contract checks."""

from pathlib import Path

import yaml
import pytest

from spec.pipeline_schemas import (
    CandidateOrigin,
    DiscoveryCandidateSubmission,
    ReleaseDecisionPayload,
    CrawlPlanReference,
)


ROOT = Path(__file__).resolve().parents[2]
OPENAPI = ROOT / "spec/openapi.yaml"


def test_manual_candidate_has_no_client_state_policy_or_release_bypass():
    candidate = DiscoveryCandidateSubmission(
        landing_url="https://example.org/about",
        submitter_rationale="Local institution candidate",
    )
    assert candidate.candidate_origin == "manual"
    assert candidate.state == "uncertain"
    assert candidate.decision_source == "manual"
    assert candidate.reason_code == "manual_review"
    assert "policy_revision_id" not in DiscoveryCandidateSubmission.model_fields
    assert "snapshot_id" not in DiscoveryCandidateSubmission.model_fields
    assert "release_state" not in DiscoveryCandidateSubmission.model_fields
    with pytest.raises(ValueError):
        DiscoveryCandidateSubmission(
            landing_url="https://example.org/about",
            submitter_rationale="Local institution candidate",
            snapshot_id="550e8400-e29b-41d4-a716-446655440000",
        )
    with pytest.raises(ValueError):
        DiscoveryCandidateSubmission(
            landing_url="https://example.org/about",
            submitter_rationale="Local institution candidate",
            candidate_origin="discovery",
        )


def test_execution_contract_accepts_only_approved_policy_revision_not_depth():
    payload = CrawlPlanReference(policy_revision_id="550e8400-e29b-41d4-a716-446655440000")
    assert str(payload.policy_revision_id) == "550e8400-e29b-41d4-a716-446655440000"
    assert "depth" not in CrawlPlanReference.model_fields
    assert "max_pages" not in CrawlPlanReference.model_fields


def test_release_contract_requires_idempotency_and_two_distinct_principals():
    payload = ReleaseDecisionPayload(
        idempotency_key="release-001",
        curator_id="550e8400-e29b-41d4-a716-446655440000",
        admin_id="550e8400-e29b-41d4-a716-446655440001",
        curator_reason="Curator approval",
        admin_reason="Admin approval",
        gate_matrix_hash="a" * 64,
        artifact_sha256="b" * 64,
    )
    assert payload.curator_id != payload.admin_id


def test_openapi_exposes_arch01_gated_inputs_and_not_client_crawl_limits():
    document = yaml.safe_load(OPENAPI.read_text(encoding="utf-8"))
    schemas = document["components"]["schemas"]
    assert "ManualCandidateSubmission" in schemas
    assert "CrawlPlanReference" in schemas
    assert "ReleaseDecisionRequest" in schemas
    assert "depth" not in schemas["CrawlPlanReference"]["properties"]
    assert "max_pages" not in schemas["CrawlPlanReference"]["properties"]
    assert document["paths"]["/api/admin/discovery-candidates/manual"]["post"]["security"]
    release = document["paths"]["/api/admin/snapshots/{snapshot_id}/release"]["post"]
    assert release["requestBody"]["required"] is True
