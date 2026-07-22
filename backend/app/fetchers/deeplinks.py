from __future__ import annotations

import re
from urllib.parse import parse_qs, quote, quote_plus, unquote_plus, urlparse

NIC_PORTAL_BASES: dict[str, str] = {
    "CPPP": "https://eprocure.gov.in/eprocure/app",
    "CPPP-eTenders": "https://etenders.gov.in/eprocure/app",
    "MP Tenders": "https://mptenders.gov.in/nicgep/app",
    "eproc.mp.gov.in": "https://eproc.mp.gov.in/nicgep/app",
    "MP PWD": "https://mptenders.gov.in/nicgep/app",
    "UP Tenders": "https://etender.up.nic.in/nicgep/app",
    "Maharashtra Tenders": "https://mahatenders.gov.in/nicgep/app",
    "Rajasthan Tenders": "https://sppp.rajasthan.gov.in/app",
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
        "https://etenders.gov.in",
        "https://etenders.gov.in/eprocure/app",
        "https://gem.gov.in",
        "https://bidplus.gem.gov.in",
        "https://bidplus.gem.gov.in/all-bids",
        "https://mptenders.gov.in",
        "https://mptenders.gov.in/nicgep/app",
        "https://eproc.mp.gov.in",
        "https://eproc.mp.gov.in/nicgep/app",
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
        "https://licindia.in",
        "https://licindia.in/tenders",
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
    r"(?:[?&]sp=S[^&\s]+|bid-details|showbidDocument|tenderRef|NIT|DirectLink)",
    flags=re.IGNORECASE,
)
NIC_PORTAL_HOSTS = frozenset(
    urlparse(base).netloc for base in NIC_PORTAL_BASES.values()
)
NIC_DIRECT_SP_RE = re.compile(r"[?&]sp=S[^&\s\"']+", flags=re.IGNORECASE)
NIC_BRITTLE_DIRECT_RE = re.compile(
    r"(?:[?&]component=%24DirectLink_0(?:[&#]|$)|[?&]page=FrontEndAdvancedSearchResult(?:[&#]|$))",
    flags=re.IGNORECASE,
)
GEM_ALL_BIDS_URL = "https://bidplus.gem.gov.in/all-bids"
GEM_DOCUMENT_PATH_RE = re.compile(
    r"(?:^|/)showbidDocument/\d+(?:[?#].*)?$", flags=re.IGNORECASE
)
GEM_REFERENCE_RE = re.compile(r"\bGEM/\d{4}/[A-Z]+/\d+\b", flags=re.IGNORECASE)
NIC_STABLE_TENDER_ID_RE = re.compile(
    r"^\d{4}_[A-Z0-9]+(?:_\d+){1,2}$", flags=re.IGNORECASE
)
AGGREGATOR_OFFICIAL_PORTAL_MARKERS: dict[str, str] = {
    "EPROCURE-ANDHRA_PRADESH": "https://tender.apeprocurement.gov.in",
    "EPROCURE-TELANGANA": "https://eprocurement.telangana.gov.in",
    "EPROCURE-MADHYA_PRADESH": NIC_PORTAL_BASES["State-MP"],
    "EPROCURE-MAHARASHTRA": NIC_PORTAL_BASES["State-MH"],
    "EPROCURE-UTTAR_PRADESH": NIC_PORTAL_BASES["State-UP"],
    "EPROCURE-RAJASTHAN": NIC_PORTAL_BASES["State-RJ"],
    "EPROCURE-CPPP": NIC_PORTAL_BASES["CPPP"],
}


def is_generic_link(url: str | None) -> bool:
    """Return True when a URL has no tender-specific identifier."""
    cleaned = (url or "").strip()
    if not cleaned:
        return True

    normalized = cleaned.rstrip("/")
    if normalized in GENERIC_HOMEPAGE_URLS:
        return True
    parsed = urlparse(cleaned)
    if parsed.scheme and parsed.netloc:
        if _is_nic_host(parsed.netloc):
            return NIC_DIRECT_SP_RE.search(cleaned) is None
        if TENDER_IDENTIFIER_RE.search(cleaned):
            return False

        path = parsed.path.strip("/")
        query = parse_qs(parsed.query)
        if not path:
            return True
        if parsed.netloc.endswith("bidplus.gem.gov.in") and path == "all-bids":
            return not _query_contains_specific_ref(query)
        if _is_aggregator_listing(parsed.netloc, path):
            return True
        if _is_aggregator_detail(parsed.netloc, path):
            return False
        if _query_contains_specific_ref(query):
            return False
        if _path_has_slug_identifier(path):
            return False
        return True

    return not _path_has_slug_identifier(cleaned)


def is_generic_homepage_url(url: str | None) -> bool:
    return is_generic_link(url)


def is_document_download_link(url: str | None) -> bool:
    cleaned = (url or "").strip()
    if not cleaned:
        return False
    parsed = urlparse(cleaned)
    return (
        parsed.netloc.endswith("bidplus.gem.gov.in")
        and GEM_DOCUMENT_PATH_RE.search(parsed.path) is not None
    )


def build_deep_link(portal: str, ref_number: str, tender_id: str | None = None) -> str:
    portal_name = (portal or "").strip()
    ref = (ref_number or "").strip()
    tid = (tender_id or "").strip()

    if tid and tid.startswith("http"):
        return tid

    if portal_name in NIC_PORTAL_BASES:
        base = NIC_PORTAL_BASES[portal_name]
        # NIC ``sp=`` values are opaque, session-bound tokens. A stable tender
        # id such as 2026_DC_505875_1 must therefore be searched, not inserted
        # into a fabricated DirectLink (which always opens "Stale Session").
        return _nic_search_link(base, nic_search_term(ref, tid))

    if portal_name == "GeM":
        direct_href = (
            _normalise_gem_card_href(tid)
            or _normalise_gem_document_id(tid)
            or _normalise_gem_card_href(ref)
        )
        if direct_href:
            return direct_href
        if ref:
            return f"{GEM_ALL_BIDS_URL}?search_bid={quote_plus(ref)}"
        return GEM_ALL_BIDS_URL

    if portal_name in {"TenderDekho", "Tender Dekho"}:
        if tid:
            last = _last_path_part(tid)
            path_prefix = "tender-detail" if last.startswith("td-") else "tender"
            return f"https://tenderdekho.com/{path_prefix}/{quote(last)}"
        if ref:
            return f"https://tenderdekho.com/tenders?search={quote_plus(ref)}"

    if portal_name in {"BidAssist", "Bid Assist"}:
        if tid:
            return f"https://bidassist.com/tenders/{quote(tid.strip('/'))}"
        if ref:
            return (
                f"https://www.google.com/search?q={quote_plus(ref)}+site:bidassist.com"
            )

    if portal_name == "LIC Tenders":
        return "https://licindia.in/tenders"

    query = f"{ref} tender".strip() or "government tender"
    return f"https://www.google.com/search?q={quote_plus(query)}"


def infer_official_link_from_aggregator(
    portal: str | None,
    ref_number: str | None,
    tender_id: str | None = None,
    *,
    title: str | None = None,
    organisation: str | None = None,
    state: str | None = None,
) -> str | None:
    """Infer an official portal target for aggregator rows.

    Aggregators often expose useful tender text but not an exact source URL.  In
    those cases, prefer the official portal search/homepage over the aggregator
    detail page.  Return None when no official source marker is identifiable.
    """
    if portal not in {"TenderDekho", "Tender Dekho", "BidAssist", "Bid Assist"}:
        return None

    text = " ".join(
        part.strip()
        for part in (
            ref_number or "",
            title or "",
            organisation or "",
            state or "",
        )
        if part and part.strip()
    )
    if not text:
        return None

    gem_ref = GEM_REFERENCE_RE.search(text)
    if gem_ref:
        return build_deep_link("GeM", gem_ref.group(0).upper(), tender_id)
    if _has_gem_marker(text):
        search_term = _aggregator_search_term(ref_number, title, organisation)
        return f"{GEM_ALL_BIDS_URL}?search_bid={quote_plus(search_term)}"

    normalized = _aggregator_marker_text(text)
    for marker, official_url in AGGREGATOR_OFFICIAL_PORTAL_MARKERS.items():
        if _aggregator_marker_text(marker) in normalized:
            if official_url in NIC_PORTAL_BASES.values():
                return _nic_search_link(
                    official_url,
                    _aggregator_search_term(ref_number, title, organisation),
                )
            return official_url
    return None


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
        if _is_aggregator_official_fallback(portal, url):
            return url, classify_link(url, False)
        url = build_deep_link(portal, ref_number, tender_id)
        return url, classify_link(url, False)
    return url, classify_link(url, captured_direct)


def extract_nic_tender_id(url: str) -> str | None:
    """Extract the NIC internal tender sp= value from a portal URL."""
    m = re.search(r"[?&]sp=([^&\s]+)", url)
    return m.group(1) if m else None


def is_stable_nic_tender_id(value: str | None) -> bool:
    return stable_nic_tender_id(value) is not None


def stable_nic_tender_id(value: str | None) -> str | None:
    tid = (value or "").strip()
    if NIC_STABLE_TENDER_ID_RE.fullmatch(tid):
        return tid
    if tid.startswith("S") and NIC_STABLE_TENDER_ID_RE.fullmatch(tid[1:]):
        return tid[1:]
    return None


def nic_search_term(ref_number: str | None, tender_id: str | None) -> str:
    """Prefer the stable NIC tender id; never search with an opaque sp token."""
    stable_id = stable_nic_tender_id(tender_id)
    if stable_id:
        return stable_id
    return (ref_number or "").strip()


def has_nic_direct_sp(url: str | None) -> bool:
    return NIC_DIRECT_SP_RE.search(url or "") is not None


def is_brittle_nic_direct_link(url: str | None) -> bool:
    cleaned = (url or "").strip()
    if not cleaned:
        return False
    parsed = urlparse(cleaned)
    return (
        _is_nic_host(parsed.netloc)
        and NIC_BRITTLE_DIRECT_RE.search(cleaned) is not None
    )


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
    decoded_tender_id = unquote_plus(tender_id.strip())
    sp_value = (
        decoded_tender_id
        if decoded_tender_id.upper().startswith("S")
        else f"S{decoded_tender_id}"
    )
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
    if (
        parsed.netloc.endswith("tenderdekho.com")
        and parsed.path.rstrip("/") == "/tenders"
    ):
        return True
    return False


def _is_nic_host(netloc: str) -> bool:
    host = netloc.casefold()
    return any(
        host == nic_host or host.endswith(f".{nic_host}")
        for nic_host in NIC_PORTAL_HOSTS
    )


def _is_aggregator_listing(netloc: str, path: str) -> bool:
    host = netloc.casefold()
    lowered_path = path.casefold().strip("/")
    if host.endswith("bidassist.com"):
        return (
            lowered_path == "all-tenders/active"
            or lowered_path.endswith("-tender/active")
            or lowered_path.endswith("-tenders/active")
        )
    return False


def _is_aggregator_detail(netloc: str, path: str) -> bool:
    host = netloc.casefold()
    lowered_path = path.casefold().strip("/")
    if host.endswith("bidassist.com"):
        return "/detail-" in f"/{lowered_path}"
    if host.endswith("tenderdekho.com"):
        return lowered_path.startswith(("tender/", "tender-detail/"))
    return False


def _is_aggregator_official_fallback(portal: str | None, url: str | None) -> bool:
    if portal not in {"TenderDekho", "Tender Dekho", "BidAssist", "Bid Assist"}:
        return False
    parsed = urlparse(url or "")
    if not parsed.scheme or not parsed.netloc:
        return False
    host = parsed.netloc.casefold()
    return not host.endswith(("tenderdekho.com", "bidassist.com"))


def _last_path_part(value: str) -> str:
    text = (value or "").strip().split("?", 1)[0].rstrip("/")
    return text.rsplit("/", 1)[-1] if "/" in text else text


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


def _normalise_gem_card_href(value: str) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    parsed = urlparse(text)
    path = parsed.path if parsed.scheme and parsed.netloc else text
    if not re.search(r"(?:^|/)showbidDocument/\d+(?:[?#].*)?$", path):
        return None
    if parsed.scheme and parsed.netloc:
        return text
    return f"https://bidplus.gem.gov.in/{path.lstrip('/')}"


def _normalise_gem_document_id(value: str) -> str | None:
    text = (value or "").strip()
    if not re.fullmatch(r"\d+", text):
        return None
    return f"https://bidplus.gem.gov.in/showbidDocument/{text}"


def _has_gem_marker(text: str) -> bool:
    return re.search(r"(?<![A-Z0-9])GEM(?:\s+(?:Goods|Service|Bid|RA)\b|\b)", text, flags=re.IGNORECASE) is not None


def _aggregator_marker_text(text: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", text.upper())


def _aggregator_search_term(
    ref_number: str | None, title: str | None, organisation: str | None
) -> str:
    ref = (ref_number or "").strip()
    if ref and not _is_low_quality_aggregator_ref(ref):
        return ref

    phrase = " ".join((title or "").split())
    for marker in (
        " Match Details ",
        " Category:",
        " Deadline ",
        " View Details",
    ):
        if marker in phrase:
            phrase = phrase.split(marker, 1)[0].strip()
    if " Posted " in phrase:
        before_posted = phrase.split(" Posted ", 1)[0].strip()
        if len(before_posted) >= 12:
            phrase = before_posted
    if phrase:
        return phrase[:140].strip()

    org = " ".join((organisation or "").split())
    return (org or ref or "printing tender")[:140].strip()


def _is_low_quality_aggregator_ref(ref_number: str) -> bool:
    ref = ref_number.strip()
    if not ref:
        return True
    if re.fullmatch(r"TD-[A-Z0-9]+", ref, flags=re.IGNORECASE):
        return True
    if re.fullmatch(r"\d{4}", ref):
        return True
    if re.fullmatch(r"[A-Z][A-Z\s-]{2,40}", ref, flags=re.IGNORECASE):
        return True
    return False
