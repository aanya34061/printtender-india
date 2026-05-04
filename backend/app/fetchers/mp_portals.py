from __future__ import annotations

import asyncio
import hashlib
import random
import re
import time
from urllib.parse import quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup, Tag
from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from app.fetchers.base import BaseFetcher, REQUEST_HEADERS, USER_AGENT
from app.fetchers.deeplinks import build_deep_link, extract_nic_tender_id

MP_STATE = "Madhya Pradesh"

MP_PRINT_KEYWORDS: list[str] = [
    "printing",
    "offset printing",
    "digital printing",
    "stationery",
    "books",
    "book",
    "forms",
    "form",
    "papers",
    "note books",
    "brochure",
    "brochures",
    "flyers",
    "visiting cards",
    "certificate",
    "certificates",
    "receipt books",
    "prospectus",
    "catalogues",
    "pass books",
    "duplex box",
    "cards",
    "answer books",
    "answer book",
    "exercise books",
    "tags",
    "poster",
    "posters",
    "banner",
    "banners",
    "label",
    "labels",
    "desk pads",
    "envelope",
    "envelopes",
    "marks sheet",
    "note sheets",
    "files",
    "pamphlet",
    "pamphlets",
    "annual report",
    "annual reports",
    "souvenir",
    "security printing",
    "textbook",
    "textbook printing",
    "gazette",
    "calendar",
    "diary",
    "sticker",
    "registers",
    "letterpress",
    "book binding",
    "packaging",
    "मुद्रण",
    "छपाई",
    "स्टेशनरी",
    "पुस्तक",
    "रजिस्टर",
    "प्रपत्र",
    "ब्रोशर",
    "पोस्टर",
    "बैनर",
    "प्रमाण पत्र",
    "डायरी",
    "कैलेंडर",
    "लेबल",
    "लिफाफा",
    "नोटबुक",
    "उत्तर पुस्तिका",
    "वार्षिक प्रतिवेदन",
]

MP_STATE_TERMS = (
    "madhya pradesh",
    "m.p.",
    " mp ",
    "bhopal",
    "indore",
    "jabalpur",
    "gwalior",
)

NIC_DIRECT_RE = re.compile(r"[?&]sp=(S[^&\s\"']+)", flags=re.IGNORECASE)
DOC_RE = re.compile(r"\.(pdf|doc|docx|xls|xlsx)(?:$|[?#])", flags=re.IGNORECASE)
TENDER_TEXT_RE = re.compile(
    r"\b(tender|nit|notice|quotation|rfp|bid)\b", flags=re.IGNORECASE
)


class _MPRecordBuilder(BaseFetcher):
    def fetch(self, keyword: str) -> list[dict]:
        return []


_builder = _MPRecordBuilder(keywords=MP_PRINT_KEYWORDS)


def _wait_between_requests() -> None:
    time.sleep(random.uniform(2, 4))


def _fetch_html(url: str, *, params: dict[str, str] | None = None) -> str:
    _wait_between_requests()
    with httpx.Client(
        timeout=30, follow_redirects=True, headers=REQUEST_HEADERS
    ) as client:
        response = client.get(url, params=params)
        response.raise_for_status()
        return response.text


def _dedupe_by_ref(tenders: list[dict]) -> list[dict]:
    deduped: list[dict] = []
    seen: set[str] = set()
    for tender in tenders:
        ref = (tender.get("ref_number") or "").strip().casefold()
        if not ref or ref in seen:
            continue
        seen.add(ref)
        deduped.append(tender)
    return deduped


def _contains_print_keyword(text: str, keyword: str | None = None) -> bool:
    normalized = text.casefold()
    if keyword and keyword.casefold() in normalized:
        return True
    return any(term.casefold() in normalized for term in MP_PRINT_KEYWORDS)


def _is_mp_text(text: str) -> bool:
    normalized = f" {text.casefold()} "
    return any(term in normalized for term in MP_STATE_TERMS)


def _first_direct_nic_link(row: Tag, base_url: str) -> tuple[str | None, str | None]:
    for anchor in row.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if not href:
            continue
        match = NIC_DIRECT_RE.search(href)
        if not match:
            continue
        portal_url = urljoin(base_url, href)
        return portal_url, match.group(1)
    return None, None


def _cell_text(columns: list[Tag], index: int) -> str:
    if len(columns) <= index:
        return ""
    return columns[index].get_text(" ", strip=True)


def _record_from_nic_row(
    *,
    row: Tag,
    keyword: str,
    base_url: str,
    portal_source: str,
) -> dict | None:
    columns = row.find_all("td")
    if len(columns) < 2:
        return None

    direct_url, tender_id = _first_direct_nic_link(row, base_url)
    row_text = row.get_text(" ", strip=True)
    ref_number = _cell_text(columns, 1) or _extract_ref(row_text)
    title = _cell_text(columns, 2) or _first_anchor_text(row) or row_text[:180]
    organisation = _cell_text(columns, 3)
    deadline = _cell_text(columns, 4)
    value = _cell_text(columns, 5)

    if not ref_number and tender_id:
        ref_number = tender_id
    if not ref_number or not title:
        return None

    portal_url = direct_url or build_deep_link(portal_source, ref_number, tender_id)
    return _builder.build_record(
        ref_number=ref_number,
        title=title,
        organisation=organisation,
        state=MP_STATE,
        portal_source=portal_source,
        deadline_raw=deadline,
        value_raw=value,
        portal_url=portal_url,
        keyword_hit=keyword,
        tender_id=tender_id,
        link_verified=bool(direct_url),
    )


def _scrape_nic_keyword_portal(
    *,
    keyword: str,
    base_url: str,
    portal_source: str,
) -> list[dict]:
    params = {
        "page": "FrontEndTendersByKeyword",
        "service": "page",
        "keyword": keyword,
        "searchBy": "0",
        "searchDateType": "TD",
    }
    try:
        html = _fetch_html(base_url, params=params)
    except Exception as exc:
        _builder.log_result(portal_source, keyword, 0, 0, "error", str(exc))
        return []

    soup = BeautifulSoup(html, "lxml")
    tenders = [
        record
        for row in soup.select("table.list_table tr, table tr")
        if (
            record := _record_from_nic_row(
                row=row, keyword=keyword, base_url=base_url, portal_source=portal_source
            )
        )
    ]
    tenders = _dedupe_by_ref(tenders)
    _builder.log_result(portal_source, keyword, len(tenders), len(tenders), "success")
    return tenders


def scrape_mp_tenders(keyword: str) -> list[dict]:
    return _scrape_nic_keyword_portal(
        keyword=keyword,
        base_url="https://mptenders.gov.in/nicgep/app",
        portal_source="MP Tenders",
    )


def scrape_mp_pwd(keyword: str) -> list[dict]:
    return _scrape_nic_keyword_portal(
        keyword=keyword,
        base_url="https://mpeprocurement.gov.in/nicgep/app",
        portal_source="MP PWD",
    )


async def scrape_gem_mp_async(keyword: str) -> list[dict]:
    portal_source = "GeM"
    url = f"https://bidplus.gem.gov.in/all-bids?search_bid={quote_plus(keyword)}"
    tenders: list[dict] = []
    seen: set[str] = set()
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        try:
            context = await browser.new_context(user_agent=USER_AGENT)
            page = await context.new_page()
            await asyncio.sleep(random.uniform(2, 4))
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            try:
                await page.wait_for_selector(
                    ".bid-list-item, .card, table tr", timeout=15000
                )
            except PlaywrightTimeoutError:
                _builder.log_result("GeM MP", keyword, 0, 0, "success")
                return []

            locators = [
                page.locator(".bid-list-item"),
                page.locator(".card"),
                page.locator("table tr"),
            ]
            for locator in locators:
                count = await locator.count()
                for index in range(count):
                    item = locator.nth(index)
                    direct_href = await _first_bid_href(item)
                    text = " ".join((await item.inner_text()).split())
                    if not text or text.casefold() in seen or not _is_mp_text(text):
                        continue
                    seen.add(text.casefold())

                    extracted_bid_number = _extract_gem_bid_number(text)
                    bid_number = extracted_bid_number or f"GeM-MP-{keyword}-{index + 1}"
                    tender_id = (
                        _gem_document_id_from_url(direct_href)
                        if direct_href
                        else extracted_bid_number
                    )
                    portal_url = (
                        urljoin("https://bidplus.gem.gov.in", direct_href)
                        if direct_href
                        else build_deep_link(portal_source, bid_number, tender_id)
                    )
                    tenders.append(
                        _builder.build_record(
                            ref_number=bid_number,
                            title=_extract_labelled_field(
                                text, ("Bid Title", "Item", "Title")
                            )
                            or text[:180],
                            organisation=_extract_labelled_field(
                                text,
                                (
                                    "Ministry",
                                    "Department",
                                    "Organisation",
                                    "Organization",
                                ),
                            ),
                            state=MP_STATE,
                            portal_source=portal_source,
                            deadline_raw=_extract_labelled_field(
                                text, ("End Date", "Bid End Date", "Closing Date")
                            ),
                            value_raw=_extract_labelled_field(
                                text, ("Value", "Estimated Bid Value", "Bid Value")
                            ),
                            portal_url=portal_url,
                            keyword_hit=keyword,
                            tender_id=tender_id,
                            link_verified=bool(direct_href),
                        )
                    )
        finally:
            await browser.close()

    tenders = _dedupe_by_ref(tenders)
    _builder.log_result("GeM MP", keyword, len(tenders), len(tenders), "success")
    return tenders


def scrape_gem_mp(keyword: str) -> list[dict]:
    try:
        return asyncio.run(scrape_gem_mp_async(keyword))
    except Exception as exc:
        _builder.log_result("GeM MP", keyword, 0, 0, "error", str(exc))
        return []


def scrape_mpbse(keyword: str) -> list[dict]:
    return _scrape_document_listing(
        keyword=keyword,
        portal_source="MPBSE",
        listing_urls=[
            "https://mpbse.nic.in/tender.html",
            "https://mpbse.nic.in/tenders.html",
            "https://mpbse.nic.in/Tender.htm",
            "https://mpbse.nic.in/",
        ],
    )


def scrape_mp_forest(keyword: str) -> list[dict]:
    return _scrape_document_listing(
        keyword=keyword,
        portal_source="MP Forest",
        listing_urls=[
            "https://mpforest.gov.in/tenders",
            "https://mpforest.gov.in/Tenders",
            "https://mpforest.gov.in/tender",
        ],
    )


def scrape_mp_info(keyword: str) -> list[dict]:
    return _scrape_document_listing(
        keyword=keyword,
        portal_source="MP Info",
        listing_urls=[
            "https://mpinfo.org/Home/Tender",
            "https://mpinfo.org/Home/Tenders",
            "https://mpinfo.org/Tender",
            "https://mpinfo.org/tenders",
        ],
        require_document=False,
    )


def scrape_all_mp_portals(keywords: list[str] | None = None) -> list[dict]:
    tenders: list[dict] = []
    for keyword in keywords or MP_PRINT_KEYWORDS:
        tenders.extend(scrape_mp_tenders(keyword))
        tenders.extend(scrape_mp_pwd(keyword))
        tenders.extend(scrape_gem_mp(keyword))
        tenders.extend(scrape_mpbse(keyword))
        tenders.extend(scrape_mp_forest(keyword))
        tenders.extend(scrape_mp_info(keyword))
    return _dedupe_by_ref(tenders)


def _scrape_document_listing(
    *,
    keyword: str,
    portal_source: str,
    listing_urls: list[str],
    require_document: bool = True,
) -> list[dict]:
    html = ""
    source_url = listing_urls[0]
    for listing_url in listing_urls:
        try:
            html = _fetch_html(listing_url)
            source_url = listing_url
            break
        except Exception:
            continue
    if not html:
        _builder.log_result(
            portal_source, keyword, 0, 0, "error", "No listing URL responded"
        )
        return []

    soup = BeautifulSoup(html, "lxml")
    tenders: list[dict] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if not href or href.startswith(("javascript:", "#", "mailto:")):
            continue
        portal_url = urljoin(source_url, href)
        context = _surrounding_text(anchor)
        if require_document and not (
            DOC_RE.search(portal_url) or TENDER_TEXT_RE.search(context)
        ):
            continue
        if not _contains_print_keyword(context, keyword):
            continue

        ref_number = _extract_ref(context) or _stable_ref(portal_source, portal_url)
        tender_id = _slug_from_url(portal_url)
        tenders.append(
            _builder.build_record(
                ref_number=ref_number,
                title=_title_from_context(context),
                organisation=portal_source,
                state=MP_STATE,
                portal_source=portal_source,
                deadline_raw=_extract_date_text(context),
                value_raw=None,
                portal_url=portal_url,
                keyword_hit=keyword,
                tender_id=tender_id,
                link_verified=True,
            )
        )

    tenders = _dedupe_by_ref(tenders)
    _builder.log_result(portal_source, keyword, len(tenders), len(tenders), "success")
    return tenders


async def _first_bid_href(item) -> str | None:
    links = item.locator("a[href*='showbidDocument']")
    if await links.count() > 0:
        return await links.first.get_attribute("href")
    links = item.locator("a[href]")
    if await links.count() > 0:
        return await links.first.get_attribute("href")
    return None


def _gem_document_id_from_url(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"showbidDocument/([^?#]+)", url)
    return match.group(1) if match else None


def _extract_gem_bid_number(text: str) -> str | None:
    match = re.search(r"\bGEM/\d{4}/B/\d+\b", text, flags=re.IGNORECASE)
    return match.group(0) if match else None


def _extract_labelled_field(text: str, labels: tuple[str, ...]) -> str | None:
    for label in labels:
        pattern = rf"{re.escape(label)}\s*:?\s*(.+?)(?=\s+[A-Z][A-Za-z ]{{2,}}\s*:|\Z)"
        match = re.search(pattern, text)
        if match:
            return match.group(1).strip()
    return None


def _first_anchor_text(row: Tag) -> str:
    anchor = row.find("a")
    return anchor.get_text(" ", strip=True) if anchor else ""


def _surrounding_text(anchor: Tag) -> str:
    parent = anchor.find_parent(["tr", "li", "p", "div"]) or anchor
    return " ".join(parent.get_text(" ", strip=True).split())


def _extract_ref(text: str) -> str | None:
    patterns = (
        r"\b[A-Z]{2,}[-/][A-Z0-9][A-Z0-9/-]{4,}\b",
        r"\bNIT\s*(?:No\.?|#|:)?\s*([A-Z0-9][A-Z0-9/-]{3,})",
        r"\bTender\s*(?:No\.?|#|:)?\s*([A-Z0-9][A-Z0-9/-]{3,})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1) if match.lastindex else match.group(0)
    return None


def _stable_ref(portal_source: str, url: str) -> str:
    digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12].upper()
    prefix = re.sub(r"[^A-Z0-9]+", "-", portal_source.upper()).strip("-")
    return f"{prefix}-{digest}"


def _slug_from_url(url: str) -> str | None:
    path = url.split("?", 1)[0].rstrip("/")
    slug = path.rsplit("/", 1)[-1]
    if not slug:
        return None
    return re.sub(r"\.(pdf|docx?|xlsx?)$", "", slug, flags=re.IGNORECASE) or None


def _title_from_context(text: str) -> str:
    compact = " ".join(text.split())
    return compact[:180] if compact else "Madhya Pradesh tender notice"


def _extract_date_text(text: str) -> str | None:
    match = re.search(r"\b\d{1,2}[-/.\s][A-Za-z0-9]{2,9}[-/.\s]\d{2,4}\b", text)
    return match.group(0) if match else None
