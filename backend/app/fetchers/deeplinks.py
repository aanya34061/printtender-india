from __future__ import annotations

import re
from urllib.parse import parse_qs, quote, quote_plus, urlparse

NIC_PORTAL_BASES: dict[str, str] = {
    "CPPP": "https://eprocure.gov.in/eprocure/app",
    "MP Tenders": "https://mptenders.gov.in/nicgep/app",
    "MP PWD": "https://mpeprocurement.gov.in/nicgep/app",
    "State-MP": "https://mptenders.gov.in/nicgep/app",
    "MP": "https://mptenders.gov.in/nicgep/app",
    "UP": "https://etender.up.nic.in/nicgep/app",
    "MH": "https://mahatenders.gov.in/nicgep/app",
    "RJ": "https://sppp.rajasthan.gov.in/app",
    "State-UP": "https://etender.up.nic.in/nicgep/app",
    "State-MH": "https://mahatenders.gov.in/nicgep/app",
    "State-RJ": "https://sppp.rajasthan.gov.in/app",
}

GENERIC_HOMEPAGE_URLS: frozenset[str] = frozenset(
    {
        "",
        "https://eprocure.gov.in",
        "https://eprocure.gov.in/eprocure/app",
        "https://gem.gov.in",
        "https://bidplus.gem.gov.in",
        "https://bidplus.gem.gov.in/all-bids",
        "https://mptenders.gov.in",
        "https://mptenders.gov.in/nicgep/app",
        "https://mpeprocurement.gov.in",
        "https://mpeprocurement.gov.in/nicgep/app",
        "https://etender.up.nic.in",
        "https://etender.up.nic.in/nicgep/app",
        "https://mahatenders.gov.in",
        "https://mahatenders.gov.in/nicgep/app",
        "https://sppp.rajasthan.gov.in",
        "https://sppp.rajasthan.gov.in/app",
        "https://tenderdekho.com",
        "https://www.tenderdekho.com",
        "https://bidassist.com",
        "https://bidassist.com/tenders",
        "https://www.bidassist.com",
        "https://www.bidassist.com/tenders",
        "https://mpbse.nic.in",
        "https://mpforest.gov.in",
        "https://mpforest.gov.in/tenders",
        "https://mpinfo.org",
    }
)

GENERIC_PATH_SEGMENTS = {
    "",
    "app",
    "all-bids",
    "tender",
    "tenders",
    "search",
    "home",
    "index",
    "notice",
    "notices",
}

TENDER_IDENTIFIER_RE = re.compile(
    r"(?:[?&]sp=S[^&\s]+|bid-details|tenderRef|NIT|DirectLink)",
    flags=re.IGNORECASE,
)


def is_generic_link(url: str | None) -> bool:
    """Return True when a URL has no tender-specific identifier."""
    cleaned = (url or "").strip()
    if not cleaned:
        return True

    normalized = cleaned.rstrip("/")
    if normalized in GENERIC_HOMEPAGE_URLS:
        return True
    if TENDER_IDENTIFIER_RE.search(cleaned):
        return False

    parsed = urlparse(cleaned)
    if parsed.scheme and parsed.netloc:
        path = parsed.path.strip("/")
        query = parse_qs(parsed.query)
        if not path:
            return True
        if _query_contains_specific_ref(query):
            return False
        if _path_has_slug_identifier(path):
            return False
        return True

    return not _path_has_slug_identifier(cleaned)


def is_generic_homepage_url(url: str | None) -> bool:
    return is_generic_link(url)


def build_deep_link(portal: str, ref_number: str, tender_id: str | None = None) -> str:
    portal_name = (portal or "").strip()
    ref = (ref_number or "").strip()
    tid = (tender_id or "").strip()

    if portal_name in NIC_PORTAL_BASES:
        base = NIC_PORTAL_BASES[portal_name]
        if tid:
            return _nic_direct_link(base, tid)
        return _nic_search_link(base, ref)

    if portal_name == "GeM":
        bid_id = tid
        if bid_id and _looks_like_gem_bid_id(bid_id):
            return f"https://bidplus.gem.gov.in/bidding/bid-details/{quote(bid_id, safe='')}"
        return f"https://bidplus.gem.gov.in/all-bids?search_bid={quote_plus(ref)}"

    if portal_name in {"TenderDekho", "Tender Dekho"}:
        if tid:
            return f"https://www.tenderdekho.com/tenders/{quote(tid.strip('/'))}"
        if ref:
            return f"https://www.google.com/search?q={quote_plus(ref)}+site:tenderdekho.com"

    if portal_name in {"BidAssist", "Bid Assist"}:
        if tid:
            return f"https://bidassist.com/tenders/{quote(tid.strip('/'))}"
        if ref:
            return (
                f"https://www.google.com/search?q={quote_plus(ref)}+site:bidassist.com"
            )

    query = f"{ref} tender".strip() or "government tender"
    return f"https://www.google.com/search?q={quote_plus(query)}"


def resolve_link(
    portal: str,
    ref_number: str,
    tender_id: str | None,
    captured_url: str | None,
    captured_direct: bool = False,
) -> tuple[str, str]:
    """Return a usable URL and its link_type."""
    url = (captured_url or "").strip()
    if is_generic_link(url):
        url = build_deep_link(portal, ref_number, tender_id)
        return url, classify_link(url, False)
    return url, classify_link(url, captured_direct)


def extract_nic_tender_id(url: str) -> str | None:
    """Extract the NIC internal tender sp= value from a portal URL."""
    m = re.search(r"[?&]sp=([^&\s]+)", url)
    return m.group(1) if m else None


def classify_link(url: str, link_verified: bool) -> str:
    """Return link_type: direct, deep, or search."""
    if is_generic_link(url):
        return "search"
    if _is_search_fallback(url):
        return "search"
    if link_verified:
        return "direct"
    return "deep"


def _nic_direct_link(base: str, tender_id: str) -> str:
    sp_value = tender_id if tender_id.upper().startswith("S") else f"S{tender_id}"
    return (
        f"{base}?component=%24DirectLink&page=FrontEndTendersByNIT"
        f"&service=direct&session=T&sp={quote_plus(sp_value)}"
    )


def _nic_search_link(base: str, ref_number: str) -> str:
    return (
        f"{base}?page=FrontEndTendersByKeyword&service=page"
        f"&keyword={quote_plus(ref_number)}&searchBy=0&searchDateType=TD"
    )


def _is_search_fallback(url: str | None) -> bool:
    parsed = urlparse(url or "")
    if "google.com" in parsed.netloc and parsed.path.startswith("/search"):
        return True
    if "bidplus.gem.gov.in" in parsed.netloc and parsed.path.rstrip("/") == "/all-bids":
        return True
    if parsed.query and "FrontEndTendersByKeyword" in parsed.query:
        return True
    return False


def _query_contains_specific_ref(query: dict[str, list[str]]) -> bool:
    for key, values in query.items():
        key_lower = key.casefold()
        if key_lower in {
            "tenderref",
            "tender_ref",
            "tenderid",
            "tender_id",
            "bidid",
            "bid_id",
        }:
            return any(value.strip() for value in values)
        if key_lower in {"keyword", "search_bid", "q"}:
            return any(_looks_like_reference(value) for value in values)
    return False


def _path_has_slug_identifier(path: str) -> bool:
    segments = [segment for segment in path.split("/") if segment]
    if not segments:
        return False
    last = segments[-1].split(".", 1)[0].casefold()
    if last in GENERIC_PATH_SEGMENTS:
        return False
    if len(segments) >= 2 and len(last) >= 4:
        return True
    return _looks_like_reference(last)


def _looks_like_reference(value: str) -> bool:
    text = (value or "").strip()
    if not text:
        return False
    if re.search(
        r"\b(?:GEM/\d{4}/B/\d+|[A-Z]{2,}[-/]\d|NIT[-/\s]?\d|\d{4}[-/][A-Z0-9])",
        text,
        flags=re.IGNORECASE,
    ):
        return True
    return bool(re.search(r"\b[A-Z0-9][A-Z0-9/-]{5,}\b", text, flags=re.IGNORECASE))


def _looks_like_gem_bid_id(value: str) -> bool:
    return bool(
        re.search(
            r"\b(?:GEM/\d{4}/B/\d+|GEM-\d{4}-B-\d+|BID-\d{4}-B-\d+)\b",
            value or "",
            flags=re.IGNORECASE,
        )
    )
