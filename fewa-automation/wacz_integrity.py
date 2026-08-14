"""Object re-read plus minimum parseable WARC/CDX replay-index validation."""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from io import BytesIO
import gzip
import json
from datetime import datetime
from urllib.parse import urlsplit
import zipfile
from typing import Protocol


class ObjectStore(Protocol):
    def read_version(self, object_key: str, version_id: str) -> bytes: ...


@dataclass(frozen=True)
class WaczVerification:
    ok: bool
    sha256: str
    reason: str | None = None


def _read_member(archive: zipfile.ZipFile, name: str) -> bytes:
    body = archive.read(name)
    return gzip.decompress(body) if name.endswith(".gz") else body


def _warc_targets(body: bytes) -> set[str]:
    # A WARC must contain a valid WARC header and at least one target URI.  We
    # intentionally parse record headers rather than accepting a file suffix.
    targets: set[str] = set()
    offset = 0
    while offset < len(body):
        # WARC records are separated by CRLF CRLF.  Only terminal whitespace
        # may remain after a record; any other bytes must begin a new header.
        while body[offset:offset + 4] == b"\r\n\r\n":
            offset += 4
        if offset == len(body):
            break
        if not body[offset:].startswith((b"WARC/1.0\r\n", b"WARC/1.1\r\n")):
            raise ValueError("WARC record header missing")
        header_end = body.find(b"\r\n\r\n", offset)
        if header_end < 0:
            raise ValueError("WARC header terminator missing")
        header = body[offset:header_end].decode("latin-1")
        lines = header.split("\r\n")
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip().lower()] = value.strip()
        record_type = headers.get("warc-type")
        target = headers.get("warc-target-uri")
        content_length = headers.get("content-length")
        if (record_type not in {"response", "resource", "request", "revisit", "metadata", "warcinfo"}
                or not headers.get("warc-record-id") or not headers.get("warc-date")
                or content_length is None or not content_length.isdigit()):
            raise ValueError("WARC required headers missing")
        try:
            datetime.fromisoformat(headers["warc-date"].replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("WARC-Date is invalid") from exc
        if record_type != "warcinfo" and (not target or urlsplit(target).scheme not in {"http", "https"}):
            raise ValueError("WARC target URI missing")
        content_start = header_end + 4
        content_end = content_start + int(content_length)
        if content_end > len(body):
            raise ValueError("WARC Content-Length does not match available body")
        if content_end < len(body) and body[content_end:content_end + 4] != b"\r\n\r\n":
            raise ValueError("WARC record framing after Content-Length is invalid")
        if target and urlsplit(target).scheme in {"http", "https"}:
            targets.add(target)
        offset = content_end
    return targets


def _index_targets(body: bytes, suffix: str) -> set[str]:
    targets: set[str] = set()
    for raw in body.decode("utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("CDX "):
            continue
        if suffix == ".cdxj":
            try:
                metadata = json.loads(line.split(" ", 2)[2])
                url = metadata.get("url")
            except (IndexError, json.JSONDecodeError):
                continue
        else:
            fields = line.split()
            url = fields[2] if len(fields) >= 3 else None
        if isinstance(url, str) and urlsplit(url).scheme in {"http", "https"}:
            targets.add(url)
    return targets


def verify_wacz(store: ObjectStore, object_key: str, version_id: str, expected_sha256: str) -> WaczVerification:
    digest = ""
    try:
        body = store.read_version(object_key, version_id)
        digest = sha256(body).hexdigest()
        if digest != expected_sha256:
            return WaczVerification(False, digest, "object_hash_mismatch")
        with zipfile.ZipFile(BytesIO(body)) as archive:
            names = archive.namelist()
            warcs = [name for name in names if name.endswith((".warc", ".warc.gz"))]
            indexes = [name for name in names if name.endswith((".cdxj", ".cdx", ".cdx.gz"))]
            if not warcs:
                return WaczVerification(False, digest, "missing_warc")
            if not indexes:
                return WaczVerification(False, digest, "missing_replay_index")
            if archive.testzip() is not None:
                return WaczVerification(False, digest, "corrupt_zip_member")
            warc_targets = set().union(*(_warc_targets(_read_member(archive, name)) for name in warcs))
            if not warc_targets:
                return WaczVerification(False, digest, "warc_parse_failed")
            index_targets = set().union(*(_index_targets(_read_member(archive, name), ".cdxj" if name.endswith(".cdxj") else ".cdx")
                                         for name in indexes))
            if not index_targets:
                return WaczVerification(False, digest, "replay_index_parse_failed")
            if not warc_targets.intersection(index_targets):
                return WaczVerification(False, digest, "replay_index_unbound")
    except ValueError:
        # A syntactically present WARC whose records cannot honour their own
        # Content-Length is an integrity failure, not a tolerated archive.
        return WaczVerification(False, digest, "warc_parse_failed")
    except Exception:
        return WaczVerification(False, digest, "object_unreadable")
    return WaczVerification(True, digest)
