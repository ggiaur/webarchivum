"""Pure, queue-safe executor plan; it never invokes Docker or a host shell."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
import json
import re
from url_security import PinnedURL, is_fewa_catalogue_url


_IMAGE = re.compile(r"^[a-z0-9][a-z0-9._/-]*@sha256:[0-9a-f]{64}$")
_JOB = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")


@dataclass(frozen=True)
class ExecutionPlan:
    seed: PinnedURL
    runtime_image_digest: str
    egress_policy_version: str
    job_id: str
    work_directory: str
    cli_args: tuple[str, ...]
    work_plan_hash: str


def build_plan(seed: PinnedURL, runtime_image_digest: str, egress_policy_version: str, *,
               job_id: str = "arch01-job", cli_version: str = "browsertrix-crawler/1.14.1") -> ExecutionPlan:
    if not _IMAGE.fullmatch(runtime_image_digest):
        raise ValueError("executor image must be an image name with an exact lowercase SHA-256 digest")
    if not _JOB.fullmatch(job_id) or not egress_policy_version or not cli_version:
        raise ValueError("job, egress policy, and Browsertrix CLI version are required")
    if is_fewa_catalogue_url(seed.canonical_url):
        raise ValueError("FEWA catalogue portal cannot be a crawl seed")
    work_directory = f"/work/jobs/{job_id}"
    cli_args = ("browsertrix-crawler", f"--cli-version={cli_version}", "crawl",
                "--config", f"{work_directory}/plan.json")
    data = {"canonical_url": seed.canonical_url, "pinned_ip": seed.pinned_ip,
            "runtime_image_digest": runtime_image_digest, "egress_policy_version": egress_policy_version,
            "job_id": job_id, "work_directory": work_directory, "cli_args": cli_args}
    return ExecutionPlan(seed, runtime_image_digest, egress_policy_version, job_id, work_directory, cli_args,
                         sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest())
