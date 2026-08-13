import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).parent.parent))
from url_security import DNSResolution, URLSecurityError, is_fewa_catalogue_url, normalize_url, resolve_and_pin


def public(_): return ["93.184.216.34", "2606:2800:220:1:248:1893:25c8:1946"]


def test_pins_complete_public_dns_answer_and_strips_fragment():
    pinned = resolve_and_pin("HTTPS://Example.com/path#x", public)
    assert pinned.canonical_url == "https://example.com/path"
    assert pinned.pinned_ip == "2606:2800:220:1:248:1893:25c8:1946"


@pytest.mark.parametrize("url", ["file:///etc/passwd", "http://127.0.0.1/", "http://2130706433/",
                                  "http://user@example.com/", "https://example.com:8080/", "https://[::1]/"])
def test_rejects_ssrf_and_url_ambiguity(url):
    with pytest.raises(URLSecurityError): normalize_url(url)


def test_mixed_dns_rejected_before_any_connection():
    with pytest.raises(URLSecurityError, match="mixed"):
        resolve_and_pin("https://example.org", lambda _: ["93.184.216.34", "169.254.169.254"])


def test_rebinding_second_resolution_cannot_inherit_first_permission():
    assert resolve_and_pin("https://example.org", lambda _: ["93.184.216.34"]).pinned_ip == "93.184.216.34"
    with pytest.raises(URLSecurityError):
        resolve_and_pin("https://example.org/next", lambda _: ["10.0.0.1"])


def test_dns_cname_chain_and_ttl_are_retained_in_the_single_connection_plan():
    pinned = resolve_and_pin("https://example.org/", lambda _: DNSResolution(
        ("93.184.216.34",), ("edge.example.org",), 60))
    assert (pinned.pinned_ip, pinned.cname_chain, pinned.dns_ttl_seconds) == (
        "93.184.216.34", ("edge.example.org",), 60)


@pytest.mark.parametrize("url", ["HTTPS://FEWA.VMK.HU./", "https://fewa.vmk.hu./tmp/x"])
def test_fewa_catalogue_authority_comparison_is_case_idna_and_root_dot_safe(url):
    assert is_fewa_catalogue_url(url)
