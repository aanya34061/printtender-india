from __future__ import annotations

import asyncio
import hashlib
import random
import re
import threading
from urllib.parse import quote_plus, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag
from playwright.async_api import async_playwright

from app.fetchers.base import BaseFetcher, REQUEST_HEADERS
from app.fetchers.deeplinks import (
    build_deep_link,
    extract_nic_tender_id,
    infer_official_link_from_aggregator,
    is_generic_link,
)


class _AggregatorRecordBuilder(BaseFetcher):
    def fetch(self, keyword: str) -> list[dict]:
        return []


_builder = _AggregatorRecordBuilder()

STATE_NAMES = (
    "Andhra Pradesh",
    "Arunachal Pradesh",
    "Assam",
    "Bihar",
    "Chhattisgarh",
    "Delhi",
    "Goa",
    "Gujarat",
    "Haryana",
    "Himachal Pradesh",
    "Jharkhand",
    "Karnataka",
    "Kerala",
    "Madhya Pradesh",
    "Maharashtra",
    "Odisha",
    "Punjab",
    "Rajasthan",
    "Tamil Nadu",
    "Telangana",
    "Uttar Pradesh",
    "Uttarakhand",
    "West Bengal",
    "Jammu And Kashmir",
    "Jammu and Kashmir",
    "Ladakh",
)

DOC_LINK_RE = re.compile(r"\.(pdf|doc|docx|xls|xlsx)(?:$|[?#])", flags=re.IGNORECASE)
BRACKETED_TENDER_RE = re.compile(
    r"^\[(?P<title>.*?)\]\s*\[(?P<ref>.*?)\]\[(?P<tender_id>.*?)\]\s*$"
)


def scrape_tenderdekho(keyword: str) -> list[dict]:
    urls = [
        ("https://tenderdekho.com/tenders", {"search": keyword}),
        ("https://tenderdekho.com/tenders", {"q": keyword}),
        ("https://tenderdekho.com/tenders", None),
    ]
    return _scrape_aggregator(
        keyword=keyword,
        portal_source="TenderDekho",
        urls=urls,
        link_predicate=_is_tenderdekho_detail_link,
    )


def scrape_bidassist(keyword: str) -> list[dict]:
    slug = re.sub(r"[^a-z0-9]+", "-", keyword.casefold()).strip("-") or "printing"
    urls = [
        (f"https://bidassist.com/{slug}-tender/active", None),
        ("https://bidassist.com/all-tenders/active", {"q": keyword}),
    ]
    return _scrape_aggregator(
        keyword=keyword,
        portal_source="BidAssist",
        urls=urls,
        link_predicate=_is_bidassist_detail_link,
        request_timeout=8,
    )


def scrape_eprocure_search(keyword: str) -> list[dict]:
    url = "https://eprocure.gov.in/eprocure/app"
    try:
        html = _fetch_eprocure_html(url, keyword)
    except Exception as exc:
        _builder.log_result("CPPP Search", keyword, 0, 0, "error", str(exc))
        return []

    soup = BeautifulSoup(html, "lxml")
    tenders: list[dict] = []
    rows = soup.select("table.list_table > tr")
    if not rows:
        rows = soup.select("table.list_table tr")
    for row in rows:
        record = _record_from_eprocure_row(row, keyword, url)
        if record:
            tenders.append(record)
    tenders = _dedupe_by_ref(tenders)
    _builder.log_result("CPPP Search", keyword, len(tenders), len(tenders), "success")
    return tenders


def _fetch_eprocure_html(url: str, keyword: str) -> str:
    params = {
        "page": "FrontEndTendersByKeyword",
        "service": "page",
        "keyword": keyword,
        "searchBy": "0",
        "searchDateType": "TD",
    }
    _builder.wait_between_requests()
    headers = {
        **REQUEST_HEADERS,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
    }
    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        if not _requires_form_search(response.text):
            return response.text

        home = client.get(url)
        home.raise_for_status()
        payload = _extract_search_form(home.text)
        payload["SearchDescription"] = keyword
        payload["Go"] = payload.get("Go") or "Go"
        form_response = client.post(url, data=payload)
        form_response.raise_for_status()
        return form_response.text


def _scrape_aggregator(
    *,
    keyword: str,
    portal_source: str,
    urls: list[tuple[str, dict[str, str] | None]],
    link_predicate: "callable",
    log: bool = True,
    request_timeout: float = 12,
) -> list[dict]:
    tenders: list[dict] = []
    last_error: str | None = None
    for url, params in urls:
        try:
            html = _fetch_html(url, params=params, timeout=request_timeout)
        except Exception as exc:
            last_error = str(exc)
            continue
        soup = BeautifulSoup(html, "lxml")
        tenders.extend(
            _records_from_detail_links(
                soup=soup,
                keyword=keyword,
                portal_source=portal_source,
                base_url=url,
                link_predicate=link_predicate,
            )
        )
        if tenders:
            break

    tenders = _dedupe_by_ref(tenders)
    status = "success" if tenders or last_error is None else "error"
    if log:
        _builder.log_result(
            portal_source,
            keyword,
            len(tenders),
            len(tenders),
            status,
            None if status == "success" else last_error,
        )
    return tenders


def _run_async(coro):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)

    result = {}

    def runner() -> None:
        try:
            result["value"] = asyncio.run(coro)
        except Exception as exc:
            result["error"] = exc

    thread = threading.Thread(target=runner)
    thread.start()
    thread.join()
    if "error" in result:
        raise result["error"]
    return result.get("value", [])


def _fetch_html(
    url: str, *, params: dict[str, str] | None = None, timeout: float = 12
) -> str:
    _builder.wait_between_requests()
    headers = {
        **REQUEST_HEADERS,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
    }
    with httpx.Client(
        timeout=timeout, follow_redirects=True, headers=headers
    ) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.text


def _requires_form_search(html: str) -> bool:
    compact = " ".join(html.split()).casefold()
    return (
        "your session in the client area has expired" in compact
        or "click here to re-login" in compact
    )


def _extract_search_form(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "lxml")
    form = soup.find("form", {"id": "tenderSearch"})
    if form is None:
        raise RuntimeError("eProcure search form not found")
    return {
        str(field.get("name")): str(field.get("value") or "")
        for field in form.find_all("input")
        if field.get("name")
    }


def _records_from_detail_links(
    *,
    soup: BeautifulSoup,
    keyword: str,
    portal_source: str,
    base_url: str,
    link_predicate: "callable",
) -> list[dict]:
    tenders: list[dict] = []
    seen_links: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if not href or href.startswith(("javascript:", "#", "mailto:")):
            continue
        portal_url = urljoin(base_url, href)
        if portal_url in seen_links or not link_predicate(portal_url):
            continue
        if is_generic_link(portal_url) or DOC_LINK_RE.search(portal_url):
            continue
        seen_links.add(portal_url)
        context = _best_context_text(anchor)
        detail_context = _detail_page_context(portal_url, portal_source)
        effective_context = " ".join(
            part for part in (context, detail_context) if part
        ).strip()
        title = (
            _detail_title(detail_context)
            or _clean_title(anchor.get_text(" ", strip=True))
            or _title_from_context(effective_context)
        )
        if not title:
            continue
        if not (
            _contains_keyword_phrase(title, keyword)
            or _contains_keyword_phrase(effective_context, keyword)
        ):
            continue
        tender_id = _slug_from_url(portal_url)
        ref_number = (
            _extract_ref(effective_context)
            or tender_id
            or _stable_ref(portal_source, portal_url)
        )
        organisation = _extract_organisation(effective_context, title)
        state = _extract_state(effective_context)
        official_url = infer_official_link_from_aggregator(
            portal_source,
            ref_number,
            tender_id,
            title=title,
            organisation=organisation,
            state=state,
        )
        tenders.append(
            _builder.build_record(
                ref_number=ref_number,
                title=title,
                organisation=organisation,
                state=state,
                portal_source=portal_source,
                deadline_raw=_extract_deadline(effective_context),
                value_raw=_extract_value(effective_context),
                portal_url=official_url or portal_url,
                keyword_hit=keyword,
                tender_id=tender_id,
                link_verified=official_url is None,
            )
        )
    return tenders


def _record_from_eprocure_row(row: Tag, keyword: str, base_url: str) -> dict | None:
    columns = row.find_all("td")
    if len(columns) < 6:
        return None

    first_col = _cell_text(columns, 0).rstrip(".")
    if not first_col.isdigit():
        return None

    row_text = row.get_text(" ", strip=True)
    direct_url = None
    tender_id = None
    for anchor in row.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        candidate = urljoin(base_url, href)
        tender_id = extract_nic_tender_id(candidate)
        if tender_id and tender_id.upper().startswith("S"):
            direct_url = candidate
            break
    if not direct_url:
        return None

    title_cell = _cell_text(columns, 4)
    title, ref_number, parsed_tender_id = _parse_bracketed_tender(title_cell)
    tender_id = tender_id or parsed_tender_id
    if not ref_number and tender_id:
        ref_number = tender_id
    if not ref_number or not title:
        return None

    portal_url = direct_url or build_deep_link("CPPP", ref_number, tender_id)
    return _builder.build_record(
        ref_number=ref_number,
        title=title,
        organisation=_cell_text(columns, 5) or _extract_organisation(row_text, title),
        state=_extract_state(row_text),
        portal_source="CPPP",
        deadline_raw=_cell_text(columns, 2) or _extract_deadline(row_text),
        value_raw=_extract_value(row_text),
        portal_url=portal_url,
        keyword_hit=keyword,
        tender_id=tender_id,
        link_verified=bool(direct_url),
    )


def _is_tenderdekho_detail_link(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.strip("/").casefold()
    return parsed.netloc.endswith("tenderdekho.com") and (
        path.startswith("tender/") or path.startswith("tender-detail/")
    )


def _is_bidassist_detail_link(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.endswith("bidassist.com") and "/detail-" in parsed.path


def _best_context_text(anchor: Tag) -> str:
    node: Tag = anchor
    best = anchor.get_text(" ", strip=True)
    for _ in range(4):
        parent = node.find_parent(["article", "li", "tr", "section", "div"])
        if parent is None:
            break
        text = " ".join(parent.get_text(" ", strip=True).split())
        if 80 <= len(text) <= 1800:
            return text
        if len(text) > len(best):
            best = text
        node = parent
    return " ".join(best.split())


def _clean_title(text: str) -> str:
    return " ".join(text.split()).strip(" -|")


def _title_from_context(text: str) -> str:
    compact = " ".join(text.split())
    if not compact:
        return ""
    for marker in (" Description:", " Details:", " Closing Date", " Deadline"):
        if marker in compact:
            compact = compact.split(marker, 1)[0]
    return compact[:180]


def _extract_ref(text: str) -> str | None:
    patterns = (
        r"\bGEM/\d{4}/[A-Z]+/\d+\b",
        r"\b(?:Tender\s*(?:ID|No\.?|Number)?|Ref(?:erence)?(?:\s*No\.?)?|TID)\s*[:#-]?\s*([A-Z0-9][A-Z0-9/_-]{3,})",
        r"\b[A-Z]{2,}[-/][A-Z0-9][A-Z0-9/-]{4,}\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1) if match.lastindex else match.group(0)
    return None


def _extract_organisation(text: str, title: str) -> str | None:
    labelled = _extract_label(
        text, ("Organisation", "Organization", "Authority", "Purchaser Name")
    )
    if labelled:
        return labelled
    match = re.match(r"(.+?)\s+Tender(?:\s+-|\b)", title, flags=re.IGNORECASE)
    return match.group(1).strip() if match else None


def _extract_state(text: str) -> str | None:
    normalized = text.casefold()
    for state in STATE_NAMES:
        if state.casefold() in normalized:
            return "Jammu and Kashmir" if state == "Jammu And Kashmir" else state
    return None


def _extract_deadline(text: str) -> str | None:
    patterns = (
        r"(?:Closing Date|Due Date|Deadline|Bid End Date|Last Date)\s*:?\s*([0-9]{1,2}\s+[A-Za-z]{3,9},?\s+[0-9]{4})",
        r"(?:Closing Date|Due Date|Deadline|Bid End Date|Last Date)\s*:?\s*([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4})",
        r"(?:Closing Date|Due Date|Deadline|Bid End Date|Last Date)\s*:?\s*([0-9]{1,2}-[A-Za-z]{3,9}-[0-9]{4})",
        r"\b[0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4}\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1) if match.lastindex else match.group(0)
    return None


def _contains_keyword_phrase(text: str, keyword: str) -> bool:
    normalized = " ".join(text.casefold().split())
    term = " ".join(keyword.casefold().split())
    if not normalized or not term:
        return False
    if any(ord(char) > 127 for char in term):
        return term in normalized

    escaped = re.escape(term).replace(r"\ ", r"\s+")
    pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
    return re.search(pattern, normalized) is not None


def _extract_value(text: str) -> str | None:
    patterns = (
        r"(?:Tender Amount|Value|Estimated Value)\s*:?\s*(₹\s*[0-9.,]+\s*(?:Lac|Lakh|Cr|Crore)?)",
        r"(₹\s*[0-9.,]+\s*(?:Lac|Lakh|Cr|Crore)?)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1)
    return None


def _extract_label(text: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*:?\s*(.+?)(?=\s+[A-Z][A-Za-z ]{{2,}}\s*:|\Z)"
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip(" |")
    return None


def _detail_page_context(url: str, portal_source: str) -> str:
    if portal_source != "BidAssist":
        return ""
    try:
        html = _fetch_html(url)
    except Exception:
        return ""
    soup = BeautifulSoup(html, "lxml")
    parts: list[str] = []
    for selector in (
        'meta[name="description"]',
        'meta[property="og:description"]',
        'meta[property="og:title"]',
        "title",
    ):
        node = soup.select_one(selector)
        if node is None:
            continue
        if node.name == "meta":
            value = node.get("content")
        else:
            value = node.get_text(" ", strip=True)
        cleaned = " ".join(str(value or "").split()).strip()
        if cleaned:
            parts.append(cleaned)
    return " ".join(dict.fromkeys(parts))


def _detail_title(detail_context: str) -> str | None:
    compact = " ".join((detail_context or "").split())
    if not compact:
        return None
    match = re.search(
        r"content=\"([^\"]+?)\s*\|\s*Closing Date",
        detail_context,
        flags=re.IGNORECASE,
    )
    if match:
        return match.group(1).strip(" -|")
    if "| Closing Date" in compact:
        return compact.split("| Closing Date", 1)[0].strip(" -|")
    return None


def _slug_from_url(url: str) -> str | None:
    path = urlparse(url).path.rstrip("/")
    slug = path.rsplit("/", 1)[-1]
    return slug or None


def _parse_bracketed_tender(text: str) -> tuple[str, str, str | None]:
    compact = " ".join(text.split())
    match = BRACKETED_TENDER_RE.match(compact)
    if not match:
        extracted_ref = _extract_ref(compact) or compact
        return compact, extracted_ref, None
    return (
        match.group("title").strip(),
        match.group("ref").strip(),
        match.group("tender_id").strip() or None,
    )


def _stable_ref(portal_source: str, url: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12].upper()
    prefix = re.sub(r"[^A-Z0-9]+", "-", portal_source.upper()).strip("-")
    return f"{prefix}-{digest}"


def _cell_text(columns: list[Tag], index: int) -> str:
    if len(columns) <= index:
        return ""
    return columns[index].get_text(" ", strip=True)


def _dedupe_by_ref(tenders: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen: set[str] = set()
    for tender in tenders:
        key = (tender.get("ref_number") or tender.get("portal_url") or "").casefold()
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(tender)
    return deduped


__all__ = [
    "scrape_bidassist",
    "scrape_eprocure_search",
    "scrape_tenderdekho",
]
