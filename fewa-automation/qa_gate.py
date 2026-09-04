"""Hash-bound release hold decision for WACZ and replay QA evidence."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Sequence, Tuple
from crawl_manifest import verify_manifest
from wacz_integrity import WaczVerification


@dataclass(frozen=True)
class ReplayEvidence:
    manifest_sha256: str
    wacz_sha256: str
    checked_at: str
    checker_id: str
    result: str  # passed | failed
    evidence_sha256: str
    replay_bad_count: int = 0
    broken_resources: Tuple[str, ...] = ()
    quality_score: float = 100.0
    max_allowed_replay_bad: int = 0

    @classmethod
    def create(
        cls,
        manifest_sha256: str,
        wacz_sha256: str,
        checked_at: str,
        checker_id: str,
        result: str,
        replay_bad_count: int = 0,
        broken_resources: Sequence[str] = (),
        quality_score: float = 100.0,
        max_allowed_replay_bad: int = 0,
    ) -> "ReplayEvidence":
        broken_tuple = tuple(sorted(broken_resources))
        payload = {
            "manifest_sha256": manifest_sha256,
            "wacz_sha256": wacz_sha256,
            "checked_at": checked_at,
            "checker_id": checker_id,
            "result": result,
            "replay_bad_count": replay_bad_count,
            "broken_resources": list(broken_tuple),
            "quality_score": quality_score,
            "max_allowed_replay_bad": max_allowed_replay_bad,
        }
        evidence_digest = sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return cls(
            manifest_sha256=manifest_sha256,
            wacz_sha256=wacz_sha256,
            checked_at=checked_at,
            checker_id=checker_id,
            result=result,
            evidence_sha256=evidence_digest,
            replay_bad_count=replay_bad_count,
            broken_resources=broken_tuple,
            quality_score=quality_score,
            max_allowed_replay_bad=max_allowed_replay_bad,
        )

    def valid_for(self, manifest_sha256: str, wacz_sha256: str) -> bool:
        if (
            self.manifest_sha256 != manifest_sha256
            or self.wacz_sha256 != wacz_sha256
            or self.result != "passed"
            or not self.checker_id
            or not self.checked_at
            or self.replay_bad_count > self.max_allowed_replay_bad
        ):
            return False
        expected = ReplayEvidence.create(
            manifest_sha256=self.manifest_sha256,
            wacz_sha256=self.wacz_sha256,
            checked_at=self.checked_at,
            checker_id=self.checker_id,
            result=self.result,
            replay_bad_count=self.replay_bad_count,
            broken_resources=self.broken_resources,
            quality_score=self.quality_score,
            max_allowed_replay_bad=self.max_allowed_replay_bad,
        ).evidence_sha256
        return self.evidence_sha256 == expected


@dataclass(frozen=True)
class QAGateResult:
    outcome: str
    reasons: tuple[str, ...]


def evaluate(
    manifest: dict[str, Any],
    *,
    wacz_ok: WaczVerification | bool,
    replay_ok: ReplayEvidence | bool,
    telemetry_complete: bool,
    verified_wacz_sha256: str | None = None,
) -> QAGateResult:
    reasons: list[str] = []
    # A truthy caller flag has no object version or SHA-256 binding. Only the
    # re-read verification result can supply positive WACZ integrity evidence.
    if not isinstance(wacz_ok, WaczVerification):
        reasons.append("wacz_integrity_evidence_invalid")
    elif not wacz_ok.ok:
        reasons.append("wacz_integrity_failed")
    elif verified_wacz_sha256 != wacz_ok.sha256:
        reasons.append("verified_wacz_digest_mismatch")
    if manifest.get("status") != "complete":
        reasons.append("crawl_incomplete")
    if not verify_manifest(manifest):
        reasons.append("manifest_hash_invalid")
    if not telemetry_complete:
        reasons.append("telemetry_incomplete")
    # wacz_ok only reports parser/integrity success; it does not identify
    # the immutable object. A release pass requires that verified digest and
    # replay evidence refer to the exact same artifact version.
    if (
        not isinstance(verified_wacz_sha256, str)
        or len(verified_wacz_sha256) != 64
        or any(char not in "0123456789abcdef" for char in verified_wacz_sha256)
    ):
        reasons.append("verified_wacz_digest_missing")
    if not isinstance(replay_ok, ReplayEvidence):
        reasons.append("replay_evidence_invalid")
    elif not isinstance(verified_wacz_sha256, str) or not replay_ok.valid_for(
        manifest.get("manifest_sha256", ""), verified_wacz_sha256
    ):
        if replay_ok.replay_bad_count > replay_ok.max_allowed_replay_bad or replay_ok.result != "passed":
            reasons.append("replay_broken_resources_detected")
        else:
            reasons.append("replay_evidence_invalid")

    if "wacz_integrity_failed" in reasons:
        return QAGateResult("integrity_failed", tuple(reasons))
    if reasons:
        return QAGateResult("review_required", tuple(reasons))
    return QAGateResult("qc_passed_pending_release", ())
