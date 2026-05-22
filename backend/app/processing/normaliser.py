from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import re
from typing import Any
from urllib.parse import urlparse

import dateparser
import pandas as pd

from app.fetchers.deeplinks import build_deep_link, classify_link, is_generic_link
from app.fetchers.base import RawTender
from app.keywords import IMAGE_PRODUCT_KEYWORDS, PRINT_KEYWORDS
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
    "GeM": "https://bidplus.gem.gov.in",
    "MP Tenders": "https://mptenders.gov.in",
    "MP PWD": "https://mpeprocurement.gov.in",
    "MPBSE": "https://mpbse.nic.in",
    "MP Forest": "https://mpforest.gov.in",
    "MP Info": "https://mpinfo.org",
    "State-MP": "https://mptenders.gov.in",
    "State-UP": "https://etender.up.nic.in",
    "State-MH": "https://mahatenders.gov.in",
    "Maharashtra Tenders": "https://mahatenders.gov.in",
    "State-RJ": "https://sppp.rajasthan.gov.in",
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
        if is_generic_link(portal_url):
            portal_url = build_deep_link(portal_source, ref_number, tender_id)
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
                "value_inr": parse_value(item.get("value_raw")),
                "portal_url": portal_url,
                "tender_id": tender_id,
                "link_type": link_type,
                "link_verified": link_verified,
                "keyword_hit": str(item.get("keyword_hit") or "").strip(),
                "keywords": keywords,
                "relevance_score": min(100, len(keywords) * 20),
                "is_active": bool(
                    bid_end_date and bid_end_date > datetime.now(timezone.utc)
                ),
                "fetched_at": item.get("fetched_at"),
            }
        )

    return pd.DataFrame(rows)


def parse_value(value: object) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0

    normalized = (
        text.replace("₹", "")
        .replace("Rs.", "")
        .replace("Rs", "")
        .replace("INR", "")
        .replace(",", "")
        .strip()
    )
    parts = normalized.split()
    try:
        amount = float(parts[0])
    except (IndexError, ValueError):
        return 0.0

    unit = " ".join(parts[1:]).casefold()
    if "lakh" in unit or "lac" in unit:
        return amount * 100000
    if "crore" in unit or "cr" in unit:
        return amount * 10000000
    return amount


def parse_bid_end_date(value: object) -> datetime | None:
    raw_text = str(value or "").strip()
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
    normalized = " ".join(text.casefold().split())
    if not normalized:
        return False
    for term in _keyword_variants(keyword):
        if any(ord(char) > 127 for char in term):
            if term in normalized:
                return True
            continue
        escaped = re.escape(term).replace(r"\ ", r"\s+")
        pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
        if re.search(pattern, normalized) is not None:
            return True
    return False


def _keyword_variants(keyword: str) -> tuple[str, ...]:
    term = " ".join(keyword.casefold().split())
    if not term:
        return ()
    variants = [term]
    if term.endswith("s") and len(term) > 3:
        variants.append(term[:-1])
    return tuple(dict.fromkeys(variants))


def find_print_keywords(text: str) -> list[str]:
    return [
        keyword
        for keyword in PRINT_KEYWORDS
        if _contains_keyword_phrase(text, keyword)
    ]


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
    searchable_text = " ".join(
        part.strip()
        for part in (title or "", organisation or "", ref_number or "")
        if part and part.strip()
    )
    keywords = set(find_product_keywords(searchable_text))
    normalized_keyword_hit = clean_optional_text(keyword_hit)
    if (
        normalized_keyword_hit
        and normalized_keyword_hit in IMAGE_PRODUCT_KEYWORDS
        and _contains_keyword_phrase(searchable_text, normalized_keyword_hit)
    ):
        keywords.add(normalized_keyword_hit)
    return keywords


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
        if is_generic_link(portal_url):
            portal_url = build_deep_link(portal_source, ref_number, tender_id)
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
            is_active=bool(bid_end_date and bid_end_date > datetime.now(timezone.utc)),
        )

    payload = asdict(raw)
    payload["title"] = " ".join(raw.title.split())
    payload["deadline"] = parse_datetime(raw.deadline)
    payload["published_at"] = parse_datetime(raw.published_at)
    payload["keywords"] = sorted(set(raw.keywords))
    return TenderCreate(**payload)
