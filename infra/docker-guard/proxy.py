"""
FEWA Docker Security Guard Proxy (infra/docker-guard/proxy.py)

A zero-trust, default-deny HTTP proxy that sits between the crawling worker
and the host Docker daemon socket (/var/run/docker.sock).

Features & Security Invariants:
1. DEFAULT-DENY: Only explicitly whitelisted endpoints/methods are forwarded.
2. CONTAINER CREATE INSPECTION (POST /containers/create):
   - Image Lock: Image name MUST start with 'webrecorder/browsertrix-crawler'.
   - Bind Mount Lock: Every bind mount host path MUST stay strictly inside /tmp/fewa_crawl_staging/ (no path traversal).
   - Privilege & Cap Lock: Privileged=false, no SYS_ADMIN/ALL capabilities.
   - Isolation Lock: NetworkMode != 'host', PidMode != 'host', IpcMode != 'host', UsernsMode != 'host'.
   - Device & Security Lock: Devices must be empty, no unconfined SecurityOpt.
3. IMAGE PULL INSPECTION (POST /images/create):
   - fromImage MUST start with 'webrecorder/browsertrix-crawler'.
"""

import asyncio
import json
import logging
import os
import re
import urllib.parse
from pathlib import Path
from typing import Dict, Any, Tuple, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] FEWA-GUARD: %(message)s")
logger = logging.getLogger("FEWA-GUARD")

DOCKER_SOCKET_PATH = os.environ.get("DOCKER_SOCKET_PATH", "/var/run/docker.sock")
LISTEN_HOST = os.environ.get("LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.environ.get("LISTEN_PORT", "2375"))
ALLOWED_STAGING_PREFIX = str(Path("/tmp/fewa_crawl_staging").resolve())
ALLOWED_IMAGE_PREFIX = "webrecorder/browsertrix-crawler"

# Regex patterns for Endpoint Whitelist (Allowlist)
# Strips optional /v1.xx API prefix
ENDPOINT_ALLOWLIST = [
    ("GET", r"^(/v\d+\.\d+)?/_ping$"),
    ("GET", r"^(/v\d+\.\d+)?/info$"),
    ("GET", r"^(/v\d+\.\d+)?/version$"),
    ("GET", r"^(/v\d+\.\d+)?/containers/[a-zA-Z0-9_\-]+/json$"),
    ("GET", r"^(/v\d+\.\d+)?/containers/[a-zA-Z0-9_\-]+/logs$"),
    ("POST", r"^(/v\d+\.\d+)?/containers/create$"),
    ("POST", r"^(/v\d+\.\d+)?/containers/[a-zA-Z0-9_\-]+/start$"),
    ("POST", r"^(/v\d+\.\d+)?/containers/[a-zA-Z0-9_\-]+/wait$"),
    ("DELETE", r"^(/v\d+\.\d+)?/containers/[a-zA-Z0-9_\-]+$"),
    ("GET", r"^(/v\d+\.\d+)?/images/[^/]+/json$"),
    ("POST", r"^(/v\d+\.\d+)?/images/create$"),
]


def is_endpoint_allowed(method: str, raw_path: str) -> bool:
    """Check if HTTP method and path match the explicit allowlist."""
    path_without_query = raw_path.split("?")[0]
    for allowed_method, p_regex in ENDPOINT_ALLOWLIST:
        if method.upper() == allowed_method and re.match(p_regex, path_without_query):
            return True
    return False


def validate_container_create_payload(body_bytes: bytes) -> Tuple[bool, str]:
    """
    Parse and validate POST /containers/create JSON payload against all security invariants.
    """
    if not body_bytes:
        return False, "Empty container creation body"

    try:
        data: Dict[str, Any] = json.loads(body_bytes.decode("utf-8"))
    except Exception as e:
        return False, f"Invalid JSON payload: {e}"

    # Rule 1: Image Lock
    image = data.get("Image", "")
    if not isinstance(image, str) or not image.lower().startswith(ALLOWED_IMAGE_PREFIX):
        return False, f"Unauthorized image '{image}'. Must start with '{ALLOWED_IMAGE_PREFIX}'"

    host_config = data.get("HostConfig") or {}
    if not isinstance(host_config, dict):
        return False, "Invalid HostConfig structure"

    # Rule 2: Bind Mount Lock (No path traversal outside /tmp/fewa_crawl_staging/)
    binds = host_config.get("Binds") or []
    if isinstance(binds, list):
        for bind in binds:
            if not isinstance(bind, str):
                return False, "Invalid bind specification"
            parts = bind.split(":")
            host_path = parts[0]
            try:
                resolved = Path(host_path).resolve()
                resolved_str = str(resolved)
            except Exception as e:
                return False, f"Invalid bind path '{host_path}': {e}"

            # Ensure host path is strictly inside ALLOWED_STAGING_PREFIX
            if not (resolved_str == ALLOWED_STAGING_PREFIX or resolved_str.startswith(ALLOWED_STAGING_PREFIX + "/")):
                return False, f"Unauthorized host bind path '{host_path}' (resolved: '{resolved_str}'). Must be within {ALLOWED_STAGING_PREFIX}"

    # Rule 3: Privilege & Capability Lock
    if host_config.get("Privileged") is True:
        return False, "Privileged containers are strictly forbidden"

    cap_add = host_config.get("CapAdd") or []
    if isinstance(cap_add, list):
        for cap in cap_add:
            if str(cap).upper() in ("SYS_ADMIN", "ALL"):
                return False, f"Forbidden CapAdd capability '{cap}'"

    # Rule 4: Host Mode Isolation Lock
    for key in ("NetworkMode", "PidMode", "IpcMode", "UsernsMode"):
        val = host_config.get(key)
        if isinstance(val, str) and val.lower() == "host":
            return False, f"Forbidden host-mode setting for '{key}'"

    # Rule 5: Device & Security Lock
    devices = host_config.get("Devices")
    if devices and isinstance(devices, list) and len(devices) > 0:
        return False, "Host device mounts are strictly forbidden"

    sec_opt = host_config.get("SecurityOpt")
    if isinstance(sec_opt, list):
        for opt in sec_opt:
            if isinstance(opt, str) and "unconfined" in opt.lower():
                return False, f"Forbidden SecurityOpt setting '{opt}'"

    return True, "OK"


def validate_image_create_query(raw_path: str) -> Tuple[bool, str]:
    """Validate POST /images/create query string (fromImage parameter)."""
    parsed = urllib.parse.urlparse(raw_path)
    query_params = urllib.parse.parse_qs(parsed.query)
    from_image = query_params.get("fromImage", [""])[0]
    if not from_image.lower().startswith(ALLOWED_IMAGE_PREFIX):
        return False, f"Unauthorized image pull '{from_image}'. Must start with '{ALLOWED_IMAGE_PREFIX}'"
    return True, "OK"


async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
    """Handle incoming TCP request from worker, inspect, and forward to Docker socket."""
    peername = writer.get_extra_info("peername")
    logger.debug(f"Client connected: {peername}")

    try:
        # Read HTTP Request headers
        header_data = bytearray()
        while b"\r\n\r\n" not in header_data:
            chunk = await reader.read(4096)
            if not chunk:
                break
            header_data.extend(chunk)

        if not header_data:
            writer.close()
            await writer.wait_closed()
            return

        header_end = header_data.find(b"\r\n\r\n")
        raw_headers_part = bytes(header_data[:header_end])
        body_part = bytes(header_data[header_end + 4:])

        lines = raw_headers_part.decode("iso-8859-1").split("\r\n")
        req_line = lines[0]
        parts = req_line.split(" ")
        if len(parts) < 2:
            writer.close()
            await writer.wait_closed()
            return

        method, path = parts[0], parts[1]

        # Read remaining body if Content-Length specified
        content_length = 0
        for header in lines[1:]:
            if ":" in header:
                k, v = header.split(":", 1)
                if k.strip().lower() == "content-length":
                    try:
                        content_length = int(v.strip())
                    except ValueError:
                        pass

        body_data = bytearray(body_part)
        while len(body_data) < content_length:
            needed = content_length - len(body_data)
            chunk = await reader.read(min(needed, 8192))
            if not chunk:
                break
            body_data.extend(chunk)

        full_body = bytes(body_data)

        # 1. Endpoint Whitelist Verification
        if not is_endpoint_allowed(method, path):
            logger.warning(f"REJECTED {method} {path} — Endpoint not in whitelist")
            resp = b"HTTP/1.1 403 Forbidden\r\nContent-Type: application/json\r\n\r\n{\"error\": \"Forbidden by FEWA Security Policy: Endpoint not whitelisted\"}"
            writer.write(resp)
            await writer.drain()
            writer.close()
            await writer.wait_closed()
            return

        # 2. Container Create Inspection
        path_without_query = path.split("?")[0]
        if method.upper() == "POST" and path_without_query.endswith("/containers/create"):
            ok, msg = validate_container_create_payload(full_body)
            if not ok:
                logger.warning(f"REJECTED {method} {path} — {msg}")
                resp = f"HTTP/1.1 403 Forbidden\r\nContent-Type: application/json\r\n\r\n{{\"error\": \"Forbidden by FEWA Security Policy: {msg}\"}}".encode("utf-8")
                writer.write(resp)
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                return

        # 3. Image Create Inspection
        if method.upper() == "POST" and path_without_query.endswith("/images/create"):
            ok, msg = validate_image_create_query(path)
            if not ok:
                logger.warning(f"REJECTED {method} {path} — {msg}")
                resp = f"HTTP/1.1 403 Forbidden\r\nContent-Type: application/json\r\n\r\n{{\"error\": \"Forbidden by FEWA Security Policy: {msg}\"}}".encode("utf-8")
                writer.write(resp)
                await writer.drain()
                writer.close()
                await writer.wait_closed()
                return

        logger.info(f"ALLOWED {method} {path}")

        # Reconstruct raw request to forward to Unix socket
        full_request = raw_headers_part + b"\r\n\r\n" + full_body

        # Forward to Docker Unix socket
        doc_reader, doc_writer = await asyncio.open_unix_connection(DOCKER_SOCKET_PATH)
        doc_writer.write(full_request)
        await doc_writer.drain()

        # Pipe response back to client
        while True:
            chunk = await doc_reader.read(8192)
            if not chunk:
                break
            writer.write(chunk)
            await writer.drain()

        doc_writer.close()
        await doc_writer.wait_closed()

    except Exception as e:
        logger.error(f"Error proxying request: {e}")
    finally:
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass


async def main():
    server = await asyncio.start_server(handle_client, LISTEN_HOST, LISTEN_PORT)
    logger.info(f"FEWA Docker Security Guard running on {LISTEN_HOST}:{LISTEN_PORT} -> {DOCKER_SOCKET_PATH}")
    async with server:
        await server.serve_forever()


if __name__ == "__main__":
    asyncio.run(main())
