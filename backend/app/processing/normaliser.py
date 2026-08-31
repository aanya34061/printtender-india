from dataclasses import asdict
from datetime import datetime, timezone
import re
from typing import Any
from urllib.parse import urlparse

import dateparser
import pandas as pd

from app.fetchers.deeplinks import (
    build_deep_link,
    classify_link,
    extract_nic_tender_id,
    is_brittle_nic_direct_link,
    is_generic_link,
)
from app.fetchers.base import RawTender
from app.keywords import IMAGE_PRODUCT_KEYWORDS, PRINT_KEYWORDS
from app.processing.relevance import (
    contains_phrase,
    extract_relevant_print_keywords,
    keyword_variants,
    matched_print_keywords,
)
from app.processing.value_parser import extract_value_text, parse_value
from app.schemas import TenderCreate


STATE_NAMES = {
    "MP": "Madhya Pradesh",
    "UP": "Uttar Pradesh",
    "MH": "Maharashtra",
    "RJ": "Rajasthan",
    "DL": "Delhi",
    "GJ": "Gujarat",
    "KA": "Karnataka",
    "TN": "Tamil Nadu",
    "WB": "West Bengal",
    "AP": "Andhra Pradesh",
}

PORTAL_BASE_URLS = {
    "CPPP": "https://eprocure.gov.in",
    "CPPP-eTenders": "https://etenders.gov.in",
    "GeM": "https://bidplus.gem.gov.in",
    "PNB Tenders": "https://pnb.bank.in",
    "Canara Bank Tenders": "https://www.canarabank.com",
    "Central Bank of India Tenders": "https://centralbankofindia.co.in",
    "Bank of India Tenders": "https://bankofindia.co.in",
    "Indian Bank Tenders": "https://indianbank.bank.in",
    "UCO Bank Tenders": "https://www.uco.bank.in",
    "Indian Overseas Bank Tenders": "https://www.iob.in",
    "LIC Tenders": "https://licindia.in",
    "MP Tenders": "https://mptenders.gov.in",
    "eproc.mp.gov.in": "https://eproc.mp.gov.in",
    "MP PWD": "https://mpeprocurement.gov.in",
    "MPBSE": "https://mpbse.nic.in",
    "MP Forest": "https://mpforest.gov.in",
    "MP Info": "https://mpinfo.org",
    "State-MP": "https://mptenders.gov.in",
    "State-UP": "https://etender.up.nic.in",
    "State-MH": "https://mahatenders.gov.in",
    "Maharashtra Tenders": "https://mahatenders.gov.in",
    "State-RJ": "https://sppp.rajasthan.gov.in",
    "Dainik Bhaskar": "https://www.bhaskar.com",
    "Patrika": "https://www.patrika.com",
    "Rajasthan Patrika": "https://www.patrika.com",
    "Nai Dunia": "https://www.naidunia.com",
    "Naidunia": "https://www.naidunia.com",
    "Nav Bharat": "https://www.navbharat.com",
    "Navbharat": "https://www.navbharat.com",
    "Dainik Jagran": "https://www.jagran.com",
    "Amar Ujala": "https://www.amarujala.com",
    "Deshbandhu": "https://deshbandhu.co.in",
    "Raj Express": "https://www.rajexpress.co",
    "Peoples Samachar": "https://peoplessamachar.in",
    "Dabang Dunia": "https://dabangdunia.co",
    "Free Press Journal": "https://www.freepressjournal.in",
    "Pradesh Today": "https://pradeshtoday.com",
    "Agniban": "https://agniban.com",
    "Nav Swadesh": "https://navswadesh.com",
    "Swadesh": "https://swadeshnews.in",
    "Hari Bhoomi": "https://www.haribhoomi.com",
    "TOI Tenders": "https://timesofindia.indiatimes.com",
    "HT Tenders": "https://hindustantimes.com",
    "ET Tenders": "https://economictimes.indiatimes.com",
    "The Hindu Tenders": "https://thehindu.com",
    "Tender Notice India": "https://tendernotice.co.in",
    "India Tender Notice": "https://indiatendernotice.com",
    "Public Notice India": "https://publicnotice.co.in",
}


def normalise(raw: list[dict]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in raw:
        ref_number = str(item.get("ref_number") or "").strip().upper()
        title = str(item.get("title") or "").strip().title()
        organisation = str(item.get("organisation") or "").strip()
        bid_end_date = parse_bid_end_date(item.get("deadline_raw"))

        if not ref_number or not title or is_past_deadline(bid_end_date):
            continue

        keywords = sorted(
            extract_matching_keywords(
                title=title,
                organisation=organisation,
                ref_number=ref_number,
                keyword_hit=item.get("keyword_hit"),
            )
        )
        if not keywords:
            continue
        portal_source = str(item.get("portal_source") or "").strip()
        tender_id = clean_optional_text(item.get("tender_id"))
        link_verified = parse_bool(item.get("link_verified"))
        portal_url = normalise_url(item.get("portal_url"), portal_source)
        rebuild_tender_id = tender_id
        if (
            is_brittle_nic_direct_link(portal_url)
            and rebuild_tender_id == extract_nic_tender_id(portal_url)
        ):
            rebuild_tender_id = None
        if is_generic_link(portal_url) or is_brittle_nic_direct_link(portal_url):
            portal_url = build_deep_link(portal_source, ref_number, rebuild_tender_id)
            link_verified = False
        link_type = clean_link_type(item.get("link_type")) or classify_link(
            portal_url, link_verified
        )
        rows.append(
            {
                "ref_number": ref_number,
                "title": title,
                "organisation": organisation,
                "state": normalise_state(item.get("state")),
                "portal_source": portal_source,
                "bid_end_date": bid_end_date,
                "value_inr": parse_value(
                    item.get("value_raw")
                    or extract_value_text(title, organisation, ref_number)
                ),
                "portal_url": portal_url,
                "tender_id": tender_id,
                "link_type": link_type,
                "link_verified": link_verified,
                "keyword_hit": str(item.get("keyword_hit") or "").strip(),
                "keywords": keywords,
                "relevance_score": min(100, len(keywords) * 20),
                "is_active": is_active_tender(portal_source, bid_end_date),
                "fetched_at": item.get("fetched_at"),
            }
        )

    return pd.DataFrame(rows)


def parse_bid_end_date(value: object) -> datetime | None:
    raw_text = str(value or "").strip()
    if not raw_text:
        return None
    try:
        if "T" in raw_text or raw_text.endswith("Z"):
            iso_text = raw_text.replace("Z", "+00:00")
            dt = datetime.fromisoformat(iso_text)
            return dt.astimezone(timezone.utc)
    except Exception:
        pass

    parsed = dateparser.parse(
        raw_text,
        settings={
            "DATE_ORDER": "DMY",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "TIMEZONE": "Asia/Kolkata",
        },
    )
    if parsed is None:
        return None
    has_explicit_time = re.search(
        r"\b\d{1,2}:\d{2}\b|\b\d{1,2}\s*(?:AM|PM)\b",
        raw_text,
        flags=re.IGNORECASE,
    ) is not None
    if not has_explicit_time:
        parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=0)
    return parsed.astimezone(timezone.utc)


def is_past_deadline(value: datetime | None) -> bool:
    return bool(value and value <= datetime.now(timezone.utc))


def is_active_tender(portal_source: str, bid_end_date: datetime | None) -> bool:
    if bid_end_date is not None:
        return bid_end_date > datetime.now(timezone.utc)
    return True


def normalise_state(value: object) -> str:
    state = str(value or "").strip()
    return STATE_NAMES.get(state.upper(), state)


def normalise_url(value: object, portal_source: object) -> str:
    url = str(value or "").strip()
    if not url:
        return ""

    parsed = urlparse(url)
    if parsed.scheme and parsed.netloc:
        if parsed.scheme == "http":
            return f"https://{parsed.netloc}{parsed.path or ''}".rstrip("/") + (
                f"?{parsed.query}" if parsed.query else ""
            )
        return url

    base_url = PORTAL_BASE_URLS.get(str(portal_source or "").strip(), "")
    if not base_url:
        return url
    if not url.startswith("/"):
        url = f"/{url}"
    return f"{base_url}{url}"


def clean_optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def parse_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().casefold() in {"1", "true", "yes", "y"}


def clean_link_type(value: object) -> str | None:
    text = str(value or "").strip()
    return text if text in {"direct", "deep", "search"} else None


def _contains_keyword_phrase(text: str, keyword: str) -> bool:
    for term in _keyword_variants(keyword):
        if contains_phrase(text, term):
            return True
    return False


def _keyword_variants(keyword: str) -> tuple[str, ...]:
    return keyword_variants(keyword)


def find_print_keywords(text: str) -> list[str]:
    return sorted(matched_print_keywords(text))


def find_product_keywords(text: str) -> list[str]:
    return [
        keyword
        for keyword in IMAGE_PRODUCT_KEYWORDS
        if _contains_keyword_phrase(text, keyword)
    ]


def extract_matching_keywords(
    *,
    title: str,
    organisation: str | None = None,
    ref_number: str | None = None,
    keyword_hit: object = None,
) -> set[str]:
    return extract_relevant_print_keywords(
        title=title,
        organisation=organisation,
        ref_number=ref_number,
        keyword_hit=keyword_hit,
    )


def _is_gem_placeholder_title(title: str) -> bool:
    normalized = " ".join((title or "").casefold().split())
    if not normalized:
        return True
    if normalized.startswith(("view", "ra no", "corrigendum", "representation")):
        return True
    if re.fullmatch(r"gem/\d{4}/[a-z]/\d+", normalized, flags=re.IGNORECASE):
        return True
    return False


def parse_datetime(value: datetime | str | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return parse_bid_end_date(value)


def normalise_tender(raw: RawTender | dict[str, Any]) -> TenderCreate | None:
    if isinstance(raw, dict):
        title = " ".join(str(raw.get("title") or "").split())
        portal_source = str(raw.get("portal_source") or raw.get("source") or "").strip()
        ref_number = (
            str(raw.get("ref_number") or raw.get("external_id") or "").strip().upper()
        )
        organisation = clean_optional_text(raw.get("organisation") or raw.get("buyer"))
        bid_end_date = parse_datetime(
            raw.get("bid_end_date") or raw.get("deadline") or raw.get("deadline_raw")
        )
        keyword_hit = clean_optional_text(raw.get("keyword_hit"))
        if (
            portal_source == "GeM"
            and keyword_hit in PRINT_KEYWORDS
            and _is_gem_placeholder_title(title)
        ):
            title = f"GeM tender for {keyword_hit} - {ref_number}"
        keywords = extract_matching_keywords(
            title=title,
            organisation=organisation,
            ref_number=ref_number,
            keyword_hit=keyword_hit,
        )
        if not keywords:
            return None
        tender_id = clean_optional_text(raw.get("tender_id"))
        link_verified = parse_bool(raw.get("link_verified"))
        portal_url = normalise_url(
            raw.get("portal_url") or raw.get("tender_url"), portal_source
        )
        rebuild_tender_id = tender_id
        if (
            is_brittle_nic_direct_link(portal_url)
            and rebuild_tender_id == extract_nic_tender_id(portal_url)
        ):
            rebuild_tender_id = None
        if is_generic_link(portal_url) or is_brittle_nic_direct_link(portal_url):
            portal_url = build_deep_link(portal_source, ref_number, rebuild_tender_id)
            link_verified = False
        link_type = clean_link_type(raw.get("link_type")) or classify_link(
            portal_url, link_verified
        )

        return TenderCreate(
            ref_number=ref_number,
            title=title,
            organisation=organisation,
            state=normalise_state(raw.get("state")),
            portal_source=portal_source,
            category=clean_optional_text(raw.get("category")),
            value_inr=parse_value(
                raw.get("value_inr")
                or raw.get("estimated_value")
                or raw.get("value_raw")
                or extract_value_text(title, organisation, ref_number)
            ),
            emd_amount=parse_value(raw.get("emd_amount")),
            bid_end_date=bid_end_date,
            published_date=parse_datetime(
                raw.get("published_date") or raw.get("published_at")
            ),
            portal_url=portal_url,
            tender_id=tender_id,
            link_type=link_type,
            link_verified=link_verified,
            keywords=sorted(keywords),
            relevance_score=min(100, len(keywords) * 20),
            is_active=is_active_tender(portal_source, bid_end_date),
        )

    payload = asdict(raw)
    payload["title"] = " ".join(raw.title.split())
    payload["deadline"] = parse_datetime(raw.deadline)
    payload["published_at"] = parse_datetime(raw.published_at)
    payload["keywords"] = sorted(set(raw.keywords))
    return TenderCreate(**payload)
