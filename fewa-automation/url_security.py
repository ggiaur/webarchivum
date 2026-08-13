"""Fail-closed URL validation and pinned-address planning for ARCH-01.

This module deliberately *plans* connections.  It never opens a socket: the
S3 egress executor must connect to ``PinnedURL.pinned_ip`` while preserving
the hostname as HTTP Host/TLS SNI.
"""
from __future__ import annotations

from dataclasses import dataclass
import ipaddress
import re
import socket
from typing import Callable, Iterable, Sequence
from urllib.parse import SplitResult, urlsplit, urlunsplit


class URLSecurityError(ValueError):
    pass


@dataclass(frozen=True)
class PinnedURL:
    original_url: str
    canonical_url: str
    hostname: str
    pinned_ip: str
    cname_chain: tuple[str, ...] = ()
    dns_ttl_seconds: int | None = None


@dataclass(frozen=True)
class DNSResolution:
    """The complete DNS evidence used for one pinned connection plan.

    Custom resolvers used by an egress implementation must return every
    terminal A/AAAA answer and the CNAME chain observed for this lookup.  The
    legacy iterable form remains accepted for small offline callers, but is
    normalised immediately and never causes a second lookup.
    """
    addresses: tuple[str, ...]
    cname_chain: tuple[str, ...] = ()
    ttl_seconds: int | None = None


def _canonical_parts(value: str) -> SplitResult:
    try:
        parts = urlsplit(value)
    except ValueError as exc:
        raise URLSecurityError("malformed URL") from exc
    if parts.scheme.lower() not in {"http", "https"}:
        raise URLSecurityError("only HTTP(S) URLs are permitted")
    if not parts.hostname or parts.username or parts.password:
        raise URLSecurityError("URL must have a hostname and no userinfo")
    try:
        port = parts.port
    except ValueError as exc:
        raise URLSecurityError("malformed URL port") from exc
    if port not in (None, 80, 443):
        raise URLSecurityError("non-default ports are prohibited")
    if port == 80 and parts.scheme.lower() != "http":
        raise URLSecurityError("non-default ports are prohibited")
    if port == 443 and parts.scheme.lower() != "https":
        raise URLSecurityError("non-default ports are prohibited")
    try:
        ipaddress.ip_address(parts.hostname)
    except ValueError:
        pass
    else:
        raise URLSecurityError("literal IP addresses are prohibited")
    # Decimal/octal/hex IPv4 spellings are intentionally rejected rather than
    # delegated to platform-specific socket parsing.
    hostname = parts.hostname.lower()
    numeric_label = re.compile(r"(?:0x[0-9a-f]+|0[0-7]*|[0-9]+)$", re.IGNORECASE)
    if hostname.replace(".", "").isdigit() or all(numeric_label.fullmatch(label) for label in hostname.split(".")):
        raise URLSecurityError("numeric host notation is prohibited")
    return parts


def normalize_url(value: str) -> str:
    """Return canonical HTTP(S) URL without a fragment, or reject it."""
    parts = _canonical_parts(value)
    try:
        host = parts.hostname.encode("idna").decode("ascii").lower()
    except UnicodeError as exc:
        raise URLSecurityError("invalid hostname") from exc
    netloc = host
    path = parts.path or "/"
    return urlunsplit((parts.scheme.lower(), netloc, path, parts.query, ""))


def _is_public(address: str) -> bool:
    ip = ipaddress.ip_address(address)
    # ``is_global`` excludes private, loopback, link-local, multicast,
    # unspecified, documentation and IPv4-mapped/private IPv6 addresses.
    return ip.is_global and not (isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped)


Resolver = Callable[[str], DNSResolution | Iterable[str]]


def system_resolver(hostname: str) -> DNSResolution:
    return DNSResolution(tuple(sorted({entry[4][0] for entry in socket.getaddrinfo(
        hostname, None, type=socket.SOCK_STREAM)})))


def _dns_resolution(value: DNSResolution | Iterable[str]) -> DNSResolution:
    if isinstance(value, DNSResolution):
        return value
    return DNSResolution(tuple(value))


def is_fewa_catalogue_url(value: str) -> bool:
    """Whether a URL points to the FEWA catalogue service itself.

    FEWA is catalogue provenance only.  Its portal and implementation
    endpoints must never cross the discovery/crawl boundary as a seed.
    """
    try:
        # Go through the same IDNA/case normalisation as a candidate URL; DNS
        # names with a terminal root dot identify the same authority.
        host = urlsplit(normalize_url(value)).hostname
    except URLSecurityError:
        return False
    if not host:
        return False
    canonical_host = host.rstrip(".").encode("idna").decode("ascii").lower()
    return canonical_host == "fewa.vmk.hu" or canonical_host.endswith(".fewa.vmk.hu")


def resolve_and_pin(value: str, resolver: Resolver = system_resolver) -> PinnedURL:
    """Validate the complete resolver answer and select a stable public IP.

    A single private/mixed answer rejects the request.  This makes DNS
    rebinding and CNAME chains fail closed when the resolver returns their full
    terminal address set.
    """
    canonical = normalize_url(value)
    host = urlsplit(canonical).hostname
    assert host is not None
    try:
        resolution = _dns_resolution(resolver(host))
        answers = sorted(set(resolution.addresses))
    except Exception as exc:
        raise URLSecurityError("DNS resolution failed") from exc
    if not answers or any(not _is_public(answer) for answer in answers):
        raise URLSecurityError("DNS answer is absent, private, or mixed")
    for cname in resolution.cname_chain:
        try:
            # CNAME hops are hostnames, never alternative IP spellings.  The
            # final A/AAAA set above is still validated as a single unit.
            if not cname or ipaddress.ip_address(cname):
                raise URLSecurityError("CNAME chain contains a literal address")
        except ValueError:
            if cname.replace(".", "").isdigit():
                raise URLSecurityError("CNAME chain contains numeric host notation")
    return PinnedURL(value, canonical, host, answers[0], tuple(resolution.cname_chain), resolution.ttl_seconds)
