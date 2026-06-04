from __future__ import annotations

import re
import subprocess
import time
import zlib
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from app.fetchers.aggregators import scrape_bidassist, scrape_tenderdekho
from app.fetchers.cppp import CPPPFetcher
from app.fetchers.deeplinks import build_deep_link, classify_link, is_brittle_nic_direct_link
from app.fetchers.mp_portals import scrape_mp_eproc
from app.fetchers.state import StateFetcher
from app.processing.normaliser import normalise_state, normalise_tender, parse_datetime, parse_value

BASE_URL = "https://mptenders.gov.in"
HOME_URL = f"{BASE_URL}/nicgep/app"
COOKIE_JAR = Path("/tmp/printtender_mp.cookies")
CACHE_TTL_SECONDS = 600
MP_STATE = "Madhya Pradesh"
MP_PORTAL = "MP Tenders"
DEFAULT_QUERY = "printing"
MH_PORTAL = "Maharashtra Tenders"

_SEARCH_CACHE: dict[str, tuple[float, list[dict]]] = {}

TITLE_REF_RE = re.compile(
    r"^\[(?P<title>.*?)\]\s*\[(?P<ref>.*?)\]\[(?P<tender_id>.*?)\]\s*$"
)


def _run_curl(args: list[str]) -> str:
    result = subprocess.run(
        ["curl", "-sS", "-L", "--max-time", "30", *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def _fetch_home_html() -> str:
    return _run_curl(["-c", str(COOKIE_JAR), "-b", str(COOKIE_JAR), HOME_URL])


def _extract_search_form(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "lxml")
    form = soup.find("form", {"id": "tenderSearch"})
    if form is None:
        raise RuntimeError("MP Tenders search form not found")

    return {
        str(field.get("name")): str(field.get("value") or "")
        for field in form.find_all("input")
        if field.get("name")
    }


def _search_html(query: str) -> str:
    home_html = _fetch_home_html()
    payload = _extract_search_form(home_html)
    payload["SearchDescription"] = query
    payload["Go"] = payload.get("Go") or "Go"

    curl_args = ["-c", str(COOKIE_JAR), "-b", str(COOKIE_JAR), "-X", "POST", HOME_URL]
    for key, value in payload.items():
        curl_args.extend(["--data-urlencode", f"{key}={value}"])
    return _run_curl(curl_args)


def _parse_dt(value: str) -> datetime | None:
    text = " ".join(value.split())
    if not text:
        return None
    try:
        return datetime.strptime(text, "%d-%b-%Y %I:%M %p").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def _parse_title_ref(value: str) -> tuple[str, str, str | None]:
    text = " ".join(value.split())
    match = TITLE_REF_RE.match(text)
    if not match:
        return text, text, None
    return (
        match.group("title").strip(),
        match.group("ref").strip(),
        match.group("tender_id").strip() or None,
    )


def _record_from_search_row(index: int, columns: list[str], href: str | None) -> dict:
    title, ref_number, tender_id = _parse_title_ref(columns[4])
    raw_portal_url = urljoin(BASE_URL, href or "/nicgep/app")
    if is_brittle_nic_direct_link(raw_portal_url):
        portal_url = build_deep_link(MP_PORTAL, ref_number, tender_id)
        link_verified = bool(tender_id)
    else:
        portal_url = raw_portal_url
        link_verified = True
    now = datetime.now(timezone.utc)
    query_terms = [term for term in (DEFAULT_QUERY,) if term]
    return {
        "id": index,
        "ref_number": ref_number,
        "title": title,
        "organisation": columns[5] if len(columns) > 5 else None,
        "state": MP_STATE,
        "portal_source": MP_PORTAL,
        "category": "printing",
        "value_inr": Decimal("0"),
        "emd_amount": Decimal("0"),
        "bid_end_date": _parse_dt(columns[2]),
        "published_date": _parse_dt(columns[1]),
        "portal_url": portal_url,
        "tender_id": tender_id,
        "link_type": classify_link(portal_url, link_verified),
        "link_verified": link_verified,
        "keywords": query_terms,
        "relevance_score": 80,
        "fetched_at": now,
        "is_active": True,
    }


def _parse_search_results(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    records: list[dict] = []
    for tr in soup.find_all("tr"):
        columns = tr.find_all("td", recursive=False)
        if len(columns) < 6:
            continue
        first = columns[0].get_text(" ", strip=True).rstrip(".")
        if not first.isdigit():
            continue
        texts = [td.get_text(" ", strip=True) for td in columns]
        href_tag = tr.find("a", href=True)
        records.append(
            _record_from_search_row(
                int(first), texts, href_tag.get("href") if href_tag else None
            )
        )
    return records


def fetch_mp_tenders(query: str | None = None) -> list[dict]:
    normalized_query = " ".join((query or DEFAULT_QUERY).split()) or DEFAULT_QUERY
    cached = _SEARCH_CACHE.get(normalized_query)
    now_monotonic = time.monotonic()
    if cached and now_monotonic - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    html = _search_html(normalized_query)
    records = _parse_search_results(html)
    _SEARCH_CACHE[normalized_query] = (now_monotonic, records)
    return records


def _fallback_record_id(portal_source: str, ref_number: str) -> int:
    payload = f"{portal_source}::{ref_number}".encode("utf-8")
    return zlib.crc32(payload) & 0x7FFFFFFF


def _serialize_fallback_record(raw: dict, portal_source: str | None = None) -> dict | None:
    payload = dict(raw)
    if portal_source:
        payload["portal_source"] = portal_source
    resolved_portal_source = str(payload.get("portal_source") or "").strip()
    tender = normalise_tender(payload)
    if tender is not None:
        data = tender.model_dump()
        data["id"] = _fallback_record_id(tender.portal_source or "", tender.ref_number)
        data["fetched_at"] = data.get("fetched_at") or datetime.now(timezone.utc)
        return data

    # Keep strict product-keyword matching for aggregator sources and only
    # fall back to the raw matched record for portal rows where the search
    # result itself is authoritative.
    if resolved_portal_source in {"BidAssist", "TenderDekho"}:
        return None

    ref_number = str(
        payload.get("ref_number") or payload.get("external_id") or ""
    ).strip().upper()
    title = " ".join(str(payload.get("title") or "").split())
    if not resolved_portal_source or not ref_number or not title:
        return None

    portal_url = str(payload.get("portal_url") or payload.get("tender_url") or "").strip()
    link_verified = bool(payload.get("link_verified"))
    return {
        "id": _fallback_record_id(resolved_portal_source, ref_number),
        "ref_number": ref_number,
        "title": title,
        "organisation": str(payload.get("organisation") or payload.get("buyer") or "").strip() or None,
        "state": normalise_state(payload.get("state")),
        "portal_source": resolved_portal_source,
        "category": str(payload.get("category") or "").strip() or "printing",
        "value_inr": parse_value(
            payload.get("value_inr") or payload.get("estimated_value") or payload.get("value_raw")
        ),
        "emd_amount": parse_value(payload.get("emd_amount")),
        "bid_end_date": parse_datetime(
            payload.get("bid_end_date") or payload.get("deadline") or payload.get("deadline_raw")
        ),
        "published_date": parse_datetime(
            payload.get("published_date") or payload.get("published_at")
        ),
        "portal_url": portal_url,
        "tender_id": str(payload.get("tender_id") or "").strip() or None,
        "link_type": str(payload.get("link_type") or classify_link(portal_url, link_verified)).strip(),
        "link_verified": link_verified,
        "keywords": [str(payload.get("keyword_hit")).strip()] if payload.get("keyword_hit") else [],
        "relevance_score": 80,
        "fetched_at": datetime.now(timezone.utc),
        "is_active": True,
    }


def _fetch_state_portal_tenders(query: str) -> list[dict]:
    rows = StateFetcher().fetch(query, "MH")
    records: list[dict] = []
    for row in rows:
        serialized = _serialize_fallback_record(row, portal_source=MH_PORTAL)
        if serialized is not None:
            records.append(serialized)
    return records


def fetch_fallback_tenders(query: str | None = None) -> list[dict]:
    normalized_query = " ".join((query or DEFAULT_QUERY).split()) or DEFAULT_QUERY
    cached = _SEARCH_CACHE.get(f"aggregate::{normalized_query}")
    now_monotonic = time.monotonic()
    if cached and now_monotonic - cached[0] < CACHE_TTL_SECONDS:
        return cached[1]

    tenders: list[dict] = []
    tenders.extend(fetch_mp_tenders(normalized_query))
    for row in scrape_mp_eproc(normalized_query):
        serialized = _serialize_fallback_record(row)
        if serialized is not None:
            tenders.append(serialized)
    for row in CPPPFetcher().fetch(normalized_query):
        serialized = _serialize_fallback_record(row)
        if serialized is not None:
            tenders.append(serialized)

    for scraper in (scrape_bidassist, scrape_tenderdekho):
        for row in scraper(normalized_query):
            serialized = _serialize_fallback_record(row)
            if serialized is not None:
                tenders.append(serialized)

    tenders.extend(_fetch_state_portal_tenders(normalized_query))

    deduped: dict[tuple[str, str], dict] = {}
    for tender in tenders:
        key = (
            str(tender.get("portal_source") or "").strip(),
            str(tender.get("ref_number") or "").strip().upper(),
        )
        deduped[key] = tender

    records = list(deduped.values())
    _SEARCH_CACHE[f"aggregate::{normalized_query}"] = (now_monotonic, records)
    return records


def _matches_filters(
    tender: dict,
    *,
    state: str | None,
    portal: str | None,
    deadline_within_days: int,
    min_value: float | None,
    max_value: float | None,
) -> bool:
    if state and tender.get("state") != state:
        return False
    if portal and tender.get("portal_source") != portal:
        return False

    deadline = tender.get("bid_end_date")
    now = datetime.now(timezone.utc)
    if isinstance(deadline, datetime):
        if deadline <= now:
            return False
        if deadline > now + timedelta(days=deadline_within_days):
            return False

    value = Decimal(str(tender.get("value_inr") or 0))
    if min_value is not None and value < Decimal(str(min_value)):
        return False
    if max_value is not None and value > Decimal(str(max_value)):
        return False
    return True


def _matches_query(tender: dict, query: str) -> bool:
    if not query:
        return True
    haystack = " ".join(
        str(
            tender.get(key) or ""
        )
        for key in ("title", "ref_number", "organisation", "state", "portal_source")
    ).casefold()
    return query.casefold() in haystack


def _sort_key(tender: dict, sort: str):
    if sort == "newest":
        return (
            -(tender.get("fetched_at") or datetime.min.replace(tzinfo=timezone.utc)).timestamp(),
            tender["id"],
        )
    if sort == "value_desc":
        return (-float(tender.get("value_inr") or 0), tender["id"])
    if sort == "value_asc":
        return (float(tender.get("value_inr") or 0), tender["id"])
    deadline = tender.get("bid_end_date") or datetime.max.replace(tzinfo=timezone.utc)
    return (deadline, tender["id"])


def list_fallback_tenders(
    *,
    q: str,
    state: str | None,
    portal: str | None,
    deadline_within_days: int,
    min_value: float | None,
    max_value: float | None,
    sort: str,
    page: int,
    limit: int,
) -> dict:
    tenders = [
        tender
        for tender in fetch_fallback_tenders(q or DEFAULT_QUERY)
        if _matches_query(tender, q)
        and _matches_filters(
            tender,
            state=state,
            portal=portal,
            deadline_within_days=deadline_within_days,
            min_value=min_value,
            max_value=max_value,
        )
    ]
    tenders.sort(key=lambda tender: _sort_key(tender, sort))
    total = len(tenders)
    offset = (page - 1) * limit
    page_rows = tenders[offset : offset + limit]
    pages = max(1, -(-total // limit))
    return {"tenders": page_rows, "total": total, "page": page, "pages": pages}


def count_fallback_tenders(
    *,
    q: str,
    state: str | None,
    portal: str | None,
    deadline_within_days: int,
    min_value: float | None,
    max_value: float | None,
) -> int:
    return list_fallback_tenders(
        q=q,
        state=state,
        portal=portal,
        deadline_within_days=deadline_within_days,
        min_value=min_value,
        max_value=max_value,
        sort="deadline_asc",
        page=1,
        limit=1000,
    )["total"]


def fallback_stats() -> dict:
    tenders = fetch_fallback_tenders(DEFAULT_QUERY)
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today_start - timedelta(days=1)
    expiring_7_days = sum(
        1
        for tender in tenders
        if tender.get("bid_end_date")
        and now < tender["bid_end_date"] <= now + timedelta(days=7)
    )
    total_today = sum(
        1
        for tender in tenders
        if tender.get("published_date") and tender["published_date"] >= today_start
    )
    new_since_yesterday = sum(
        1
        for tender in tenders
        if tender.get("published_date")
        and yesterday_start <= tender["published_date"] < today_start
    )
    by_portal: dict[str, int] = {}
    states: set[str] = set()
    for tender in tenders:
        portal = str(tender.get("portal_source") or "").strip()
        state = str(tender.get("state") or "").strip()
        if portal:
            by_portal[portal] = by_portal.get(portal, 0) + 1
        if state:
            states.add(state)
    return {
        "total_active": len(tenders),
        "total_today": total_today,
        "expiring_7_days": expiring_7_days,
        "new_since_yesterday": new_since_yesterday,
        "states_covered": len(states),
        "by_portal": by_portal,
        "by_source_category": {"portal": len(tenders), "newspaper": 0},
        "last_fetch": now,
        "portals_count": len(by_portal),
        "keywords_tracked": 0,
    }


def get_fallback_tender(tender_id: int) -> dict | None:
    for tender in fetch_fallback_tenders(DEFAULT_QUERY):
        if tender.get("id") == tender_id:
            return tender
    return None
