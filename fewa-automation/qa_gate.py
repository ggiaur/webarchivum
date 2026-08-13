"""Hash-bound release hold decision for WACZ and replay QA evidence."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any
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

    @classmethod
    def create(cls, manifest_sha256: str, wacz_sha256: str, checked_at: str,
               checker_id: str, result: str) -> "ReplayEvidence":
        payload = {"manifest_sha256": manifest_sha256, "wacz_sha256": wacz_sha256,
                   "checked_at": checked_at, "checker_id": checker_id, "result": result}
        return cls(**payload, evidence_sha256=sha256(json.dumps(payload, sort_keys=True,
                                                                   separators=(",", ":")).encode()).hexdigest())

    def valid_for(self, manifest_sha256: str, wacz_sha256: str) -> bool:
        if (self.manifest_sha256 != manifest_sha256 or self.wacz_sha256 != wacz_sha256
                or self.result != "passed" or not self.checker_id or not self.checked_at):
            return False
        expected = ReplayEvidence.create(self.manifest_sha256, self.wacz_sha256, self.checked_at,
                                         self.checker_id, self.result).evidence_sha256
        return self.evidence_sha256 == expected


@dataclass(frozen=True)
class QAGateResult:
    outcome: str
    reasons: tuple[str, ...]


def evaluate(manifest: dict[str, Any], *, wacz_ok: WaczVerification | bool, replay_ok: ReplayEvidence | bool,
             telemetry_complete: bool, verified_wacz_sha256: str | None = None) -> QAGateResult:
    reasons: list[str] = []
    # A truthy caller flag has no object version or SHA-256 binding.  Only the
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
    # ``wacz_ok`` only reports parser/integrity success; it does not identify
    # the immutable object.  A release pass requires that verified digest and
    # replay evidence refer to the exact same artifact version.
    if (not isinstance(verified_wacz_sha256, str) or len(verified_wacz_sha256) != 64
            or any(char not in "0123456789abcdef" for char in verified_wacz_sha256)):
        reasons.append("verified_wacz_digest_missing")
    if (not isinstance(replay_ok, ReplayEvidence)
            or not isinstance(verified_wacz_sha256, str)
            or not replay_ok.valid_for(manifest.get("manifest_sha256", ""), verified_wacz_sha256)):
        reasons.append("replay_evidence_invalid")
    if "wacz_integrity_failed" in reasons:
        return QAGateResult("integrity_failed", tuple(reasons))
    if reasons:
        return QAGateResult("review_required", tuple(reasons))
    return QAGateResult("qc_passed_pending_release", ())
