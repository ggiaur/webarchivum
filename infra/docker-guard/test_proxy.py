"""
Unit and Adversarial Security Tests for FEWA Docker Security Guard (infra/docker-guard/proxy.py)
"""

import json
import sys
from pathlib import Path
import pytest

_GUARD_DIR = Path(__file__).resolve().parent
if str(_GUARD_DIR) not in sys.path:
    sys.path.insert(0, str(_GUARD_DIR))

from proxy import (
    is_endpoint_allowed,
    validate_container_create_payload,
    validate_image_create_query,
)


def test_endpoint_allowlist():
    """Verify that only explicitly permitted endpoints pass the allowlist."""
    # Allowed endpoints
    assert is_endpoint_allowed("GET", "/_ping") is True
    assert is_endpoint_allowed("GET", "/v1.43/_ping") is True
    assert is_endpoint_allowed("GET", "/v1.43/info") is True
    assert is_endpoint_allowed("GET", "/v1.43/version") is True
    assert is_endpoint_allowed("GET", "/v1.43/containers/c123/json") is True
    assert is_endpoint_allowed("GET", "/v1.43/containers/c123/logs") is True
    assert is_endpoint_allowed("POST", "/v1.43/containers/create") is True
    assert is_endpoint_allowed("POST", "/containers/create") is True
    assert is_endpoint_allowed("POST", "/v1.43/containers/c123/start") is True
    assert is_endpoint_allowed("POST", "/v1.43/containers/c123/wait") is True
    assert is_endpoint_allowed("DELETE", "/v1.43/containers/c123") is True
    assert is_endpoint_allowed("GET", "/v1.43/images/browsertrix/json") is True
    assert is_endpoint_allowed("POST", "/v1.43/images/create?fromImage=webrecorder/browsertrix-crawler") is True

    # Forbidden endpoints (Default-Deny)
    assert is_endpoint_allowed("DELETE", "/v1.43/volumes/vol1") is False
    assert is_endpoint_allowed("POST", "/v1.43/exec/e123/start") is False
    assert is_endpoint_allowed("POST", "/v1.43/swarm/init") is False
    assert is_endpoint_allowed("POST", "/v1.43/services/create") is False
    assert is_endpoint_allowed("GET", "/v1.43/events") is False
    assert is_endpoint_allowed("POST", "/v1.43/containers/c123/exec") is False


def test_valid_container_create():
    """Verify clean Browsertrix container payload passes inspection."""
    payload = {
        "Image": "webrecorder/browsertrix-crawler:latest",
        "Cmd": ["crawl", "--url", "https://example.hu"],
        "HostConfig": {
            "Binds": ["/tmp/fewa_crawl_staging/job-101:/crawls"],
            "ShmSize": 1073741824,
            "AutoRemove": True,
        },
    }
    ok, msg = validate_container_create_payload(json.dumps(payload).encode("utf-8"))
    assert ok is True
    assert msg == "OK"


def test_reject_unauthorized_image():
    """Adversarial test: attempt to create non-Browsertrix container."""
    payload = {
        "Image": "ubuntu:latest",
        "HostConfig": {"Binds": ["/tmp/fewa_crawl_staging/job-101:/crawls"]},
    }
    ok, msg = validate_container_create_payload(json.dumps(payload).encode("utf-8"))
    assert ok is False
    assert "Unauthorized image" in msg


def test_reject_path_traversal_bind():
    """Adversarial test: path traversal attempting to mount host root."""
    payload = {
        "Image": "webrecorder/browsertrix-crawler:latest",
        "HostConfig": {"Binds": ["/tmp/fewa_crawl_staging/../../etc:/crawls"]},
    }
    ok, msg = validate_container_create_payload(json.dumps(payload).encode("utf-8"))
    assert ok is False
    assert "Unauthorized host bind path" in msg


def test_reject_host_root_bind():
    """Adversarial test: direct mount of host root directory."""
    payload = {
        "Image": "webrecorder/browsertrix-crawler:latest",
        "HostConfig": {"Binds": ["/:/host_root"]},
    }
    ok, msg = validate_container_create_payload(json.dumps(payload).encode("utf-8"))
    assert ok is False
    assert "Unauthorized host bind path" in msg


def test_reject_privileged_container():
    """Adversarial test: attempt to enable privileged mode."""
    payload = {
        "Image": "webrecorder/browsertrix-crawler:latest",
        "HostConfig": {
            "Binds": ["/tmp/fewa_crawl_staging/job-101:/crawls"],
            "Privileged": True,
        },
    }
    ok, msg = validate_container_create_payload(json.dumps(payload).encode("utf-8"))
    assert ok is False
    assert "Privileged containers are strictly forbidden" in msg


def test_reject_forbidden_cap_add():
    """Adversarial test: attempt to add SYS_ADMIN capability."""
    payload = {
        "Image": "webrecorder/browsertrix-crawler:latest",
        "HostConfig": {
            "Binds": ["/tmp/fewa_crawl_staging/job-101:/crawls"],
            "CapAdd": ["SYS_ADMIN"],
        },
    }
    ok, msg = validate_container_create_payload(json.dumps(payload).encode("utf-8"))
    assert ok is False
    assert "Forbidden CapAdd capability" in msg


def test_reject_host_network_mode():
    """Adversarial test: attempt to set host network mode."""
    payload = {
        "Image": "webrecorder/browsertrix-crawler:latest",
        "HostConfig": {
            "Binds": ["/tmp/fewa_crawl_staging/job-101:/crawls"],
            "NetworkMode": "host",
        },
    }
    ok, msg = validate_container_create_payload(json.dumps(payload).encode("utf-8"))
    assert ok is False
    assert "Forbidden host-mode setting" in msg


def test_reject_host_devices():
    """Adversarial test: attempt to mount host devices."""
    payload = {
        "Image": "webrecorder/browsertrix-crawler:latest",
        "HostConfig": {
            "Binds": ["/tmp/fewa_crawl_staging/job-101:/crawls"],
            "Devices": [{"PathOnHost": "/dev/sda"}],
        },
    }
    ok, msg = validate_container_create_payload(json.dumps(payload).encode("utf-8"))
    assert ok is False
    assert "Host device mounts are strictly forbidden" in msg


def test_reject_unconfined_security_opt():
    """Adversarial test: attempt to disable seccomp/apparmor profiles."""
    payload = {
        "Image": "webrecorder/browsertrix-crawler:latest",
        "HostConfig": {
            "Binds": ["/tmp/fewa_crawl_staging/job-101:/crawls"],
            "SecurityOpt": ["seccomp=unconfined"],
        },
    }
    ok, msg = validate_container_create_payload(json.dumps(payload).encode("utf-8"))
    assert ok is False
    assert "Forbidden SecurityOpt setting" in msg


def test_image_create_query_validation():
    """Verify image pull query string validation."""
    # Valid image pull
    ok, msg = validate_image_create_query("/v1.43/images/create?fromImage=webrecorder/browsertrix-crawler:latest")
    assert ok is True

    # Malicious image pull
    ok, msg = validate_image_create_query("/v1.43/images/create?fromImage=malicious/hacker-image:latest")
    assert ok is False
    assert "Unauthorized image pull" in msg
