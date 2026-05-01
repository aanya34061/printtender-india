from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import dateparser
import pandas as pd

from app.fetchers.base import PRINT_KEYWORDS, RawTender
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
    "State-MP": "https://mptenders.gov.in",
    "State-UP": "https://etender.up.nic.in",
    "State-MH": "https://mahatenders.gov.in",
    "State-RJ": "https://sppp.rajasthan.gov.in",
}


def normalise(raw: list[dict]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for item in raw:
        ref_number = str(item.get("ref_number") or "").strip().upper()
        title = str(item.get("title") or "").strip().title()
        bid_end_date = parse_bid_end_date(item.get("deadline_raw"))

        if not ref_number or not title or is_past_deadline(bid_end_date):
            continue

        keywords = find_print_keywords(title)
        rows.append(
            {
                "ref_number": ref_number,
                "title": title,
                "organisation": str(item.get("organisation") or "").strip(),
                "state": normalise_state(item.get("state")),
                "portal_source": str(item.get("portal_source") or "").strip(),
                "bid_end_date": bid_end_date,
                "value_inr": parse_value(item.get("value_raw")),
                "portal_url": normalise_url(
                    item.get("portal_url"), item.get("portal_source")
                ),
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
    parsed = dateparser.parse(
        str(value or ""),
        settings={
            "DATE_ORDER": "DMY",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "TO_TIMEZONE": "UTC",
        },
    )
    if parsed is None:
        return None
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


def find_print_keywords(title: str) -> list[str]:
    normalized = title.casefold()
    return [keyword for keyword in PRINT_KEYWORDS if keyword.casefold() in normalized]


def parse_datetime(value: datetime | str | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return parse_bid_end_date(value)


def normalise_tender(raw: RawTender) -> TenderCreate:
    payload = asdict(raw)
    payload["title"] = " ".join(raw.title.split())
    payload["deadline"] = parse_datetime(raw.deadline)
    payload["published_at"] = parse_datetime(raw.published_at)
    payload["keywords"] = sorted(set(raw.keywords))
    return TenderCreate(**payload)
