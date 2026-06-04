from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from typing import Any, Iterable
from urllib.parse import quote, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from app.fetchers.base import BaseFetcher, REQUEST_HEADERS


DOC_LINK_RE = re.compile(
    r"\.(pdf|doc|docx|xls|xlsx|zip)(?:$|[?#])",
    flags=re.IGNORECASE,
)
DATE_LINE_RE = re.compile(
    r"(?:last\s+date(?:\s+of\s+submission(?:\s+of\s+tender)?)?|bid\s+submission\s+end\s+date|"
    r"closing\s+date|due\s+date|submission\s+date|end\s+date)\s*[:\-]?\s*([^\n|]{6,80})",
    flags=re.IGNORECASE,
)
REF_PATTERNS = (
    re.compile(r"\bGEM/\d{4}/B/\d+\b", flags=re.IGNORECASE),
    re.compile(
        r"\b(?:REF(?:ERENCE)?(?:\s*(?:NO|NUMBER))?|REF|NIT|RFP|TENDER(?:\s*(?:NO|ID|REF(?:ERENCE)?))?)"
        r"\s*[:#-]?\s*([A-Z0-9][A-Z0-9/._-]{3,})\b",
        flags=re.IGNORECASE,
    ),
)
REFERENCE_STOPWORDS = {
    "THROUGH",
    "PORTAL",
    "TENDER",
    "DOCUMENT",
    "DOWNLOAD",
    "NOTICE",
}
TITLE_NOISE_RE = re.compile(
    r"\b(?:technical bid|price bid|download|notice|view details|corrigendum|addendum|amendment|"
    r"general|specification|annexure(?:\s+[a-z0-9]+)?|gem rfp|nit\s*&\s*tender)\b",
    flags=re.IGNORECASE,
)
HTML_CACHE_TTL_SECONDS = 300
HTML_CACHE: dict[str, tuple[float, str]] = {}


@dataclass(frozen=True)
class BankPortal:
    source: str
    url: str
    organisation: str
    state: str = "India"
    mode: str = "html"


BANK_PORTALS: dict[str, BankPortal] = {
    "PNB Tenders": BankPortal(
        source="PNB Tenders",
        url="https://pnb.bank.in/Tender.aspx",
        organisation="Punjab National Bank",
    ),
    "Canara Bank Tenders": BankPortal(
        source="Canara Bank Tenders",
        url="https://www.canarabank.bank.in/tenders",
        organisation="Canara Bank",
        mode="canara_api",
    ),
    "Central Bank of India Tenders": BankPortal(
        source="Central Bank of India Tenders",
        url="https://centralbank.bank.in/en/active-tender",
        organisation="Central Bank of India",
        mode="central_table",
    ),
    "Bank of India Tenders": BankPortal(
        source="Bank of India Tenders",
        url="https://bankofindia.co.in/tenders",
        organisation="Bank of India",
    ),
    "Indian Bank Tenders": BankPortal(
        source="Indian Bank Tenders",
        url="https://indianbank.bank.in/tenders/",
        organisation="Indian Bank",
    ),
    "UCO Bank Tenders": BankPortal(
        source="UCO Bank Tenders",
        url="https://www.uco.bank.in/tenders",
        organisation="UCO Bank",
    ),
    "Indian Overseas Bank Tenders": BankPortal(
        source="Indian Overseas Bank Tenders",
        url="https://www.iob.in/",
        organisation="Indian Overseas Bank",
    ),
    "LIC Tenders": BankPortal(
        source="LIC Tenders",
        url="https://licindia.in/tenders",
        organisation="Life Insurance Corporation of India",
        mode="lic_table",
    ),
}


class BankPortalFetcher(BaseFetcher):
    def __init__(self, portal: BankPortal) -> None:
        super().__init__()
        self.portal = portal

    def fetch(self, keyword: str) -> list[dict]:
        try:
            if self.portal.mode == "canara_api":
                tenders = self._fetch_canara_api(keyword)
            elif self.portal.mode == "central_table":
                tenders = self._fetch_central_table(keyword)
            elif self.portal.mode == "lic_table":
                tenders = self._fetch_lic_table(keyword)
            else:
                html = _fetch_html(self.portal.url)
                if self.portal.source == "PNB Tenders":
                    tenders = self._parse_pnb_html(html, keyword)
                else:
                    tenders = self._parse_html(html, keyword)
            self.log_result(
                self.portal.source, keyword, len(tenders), len(tenders), "success"
            )
            return tenders
        except Exception as exc:
            self.log_result(self.portal.source, keyword, 0, 0, "error", str(exc))
            return []

    def _parse_html(self, html: str, keyword: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        tenders: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for container in _candidate_containers(soup):
            text = _compact_ws(container.get_text(" ", strip=True))
            if not text or not _contains_keyword_phrase(text, keyword):
                continue

            links = _container_links(container, self.portal.url)
            if not links:
                continue

            portal_url = _choose_best_link(links)
            ref_number = _extract_reference(text, portal_url)
            title = _extract_title(container, text, self.portal.organisation)
            if not title:
                continue

            key = ((ref_number or "").casefold(), portal_url.casefold())
            if key in seen:
                continue
            seen.add(key)

            tenders.append(
                self.build_record(
                    ref_number=ref_number,
                    title=title,
                    organisation=self.portal.organisation,
                    state=self.portal.state,
                    portal_source=self.portal.source,
                    deadline_raw=_extract_deadline(text),
                    value_raw="",
                    portal_url=portal_url,
                    keyword_hit=keyword,
                    tender_id=None,
                    link_verified=True,
                )
            )
        return tenders

    def _parse_pnb_html(self, html: str, keyword: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        rows = soup.select("a[id*='rptGrid_lbtnTenderTitle_']")
        if not rows:
            return self._parse_html(html, keyword)

        tenders: list[dict] = []
        seen: set[str] = set()
        for anchor in rows:
            row = anchor.find_parent("tr")
            if row is None:
                continue
            title = _compact_ws(anchor.get_text(" ", strip=True))
            office = _compact_ws(
                (row.select_one("span[id*='rptGrid_Label1_']") or row).get_text(
                    " ", strip=True
                )
            )
            deadline_text = _compact_ws(
                (row.select_one("span[id*='rptGrid_Label2_']") or row).get_text(
                    " ", strip=True
                )
            )
            text = _compact_ws(" ".join(part for part in (office, title) if part))
            if not text or not _contains_keyword_phrase(text, keyword):
                continue
            ref_number = _extract_reference(title, self.portal.url)
            if ref_number.casefold() in seen:
                continue
            seen.add(ref_number.casefold())
            tenders.append(
                self.build_record(
                    ref_number=ref_number,
                    title=title,
                    organisation=office or self.portal.organisation,
                    state=self.portal.state,
                    portal_source=self.portal.source,
                    deadline_raw=deadline_text,
                    value_raw="",
                    portal_url=self.portal.url,
                    keyword_hit=keyword,
                    tender_id=None,
                    link_verified=False,
                )
            )
        return tenders

    def _fetch_lic_table(self, keyword: str) -> list[dict]:
        html = _fetch_html(self.portal.url)
        soup = BeautifulSoup(html, "lxml")
        table = soup.select_one("table#tableID")
        if table is None:
            return []
        tenders: list[dict] = []
        seen: set[str] = set()

        rows = table.select("tbody tr") or table.select("tr")
        for row in rows:
            cells = [
                _compact_ws(cell.get_text(" ", strip=True))
                for cell in row.find_all(["td", "th"], recursive=False)
            ]
            if len(cells) < 4:
                continue

            region, department, title, listed_date = cells[:4]
            if not title or title.casefold() == "tender description":
                continue

            text = _compact_ws(" ".join([region, department, title]))
            if not _contains_keyword_phrase(text, keyword):
                continue

            links = _container_links(row, self.portal.url)
            ref_number = _extract_lic_reference(title, region, department, listed_date)
            if links:
                portal_url = _choose_best_link(links)
            elif onclick_link := _extract_lic_onclick_link(row):
                portal_url = urljoin(self.portal.url, onclick_link)
            elif ref_number.startswith("GEM/"):
                portal_url = (
                    "https://bidplus.gem.gov.in/all-bids"
                    f"?search_bid={quote(ref_number)}"
                )
            else:
                portal_url = self.portal.url
            if ref_number.casefold() in seen:
                continue
            seen.add(ref_number.casefold())

            organisation = _compact_ws(
                " - ".join(
                    part
                    for part in (self.portal.organisation, region, department)
                    if part
                )
            )
            tenders.append(
                self.build_record(
                    ref_number=ref_number,
                    title=title,
                    organisation=organisation,
                    state=self.portal.state,
                    portal_source=self.portal.source,
                    deadline_raw="",
                    value_raw="",
                    portal_url=portal_url,
                    keyword_hit=keyword,
                    tender_id=None,
                    link_verified=bool(links or portal_url != self.portal.url),
                )
            )
        return tenders

    def _fetch_canara_api(self, keyword: str) -> list[dict]:
        normalized_keyword = keyword.strip().replace("'", "")
        if not normalized_keyword:
            return []
        filter_expr = (
            f"contains(descriptionEnglish,'{normalized_keyword}')"
            f" or contains(tenderRefNo,'{normalized_keyword}')"
            f" or contains(issuedBy,'{normalized_keyword}')"
        )
        encoded_filter = quote(filter_expr, safe="(),' ")
        api_url = (
            "https://www.canarabank.bank.in/o/c/tendersmasters/"
            f"?page=1&pageSize=50&filter={encoded_filter}"
        )
        payload = _fetch_json(api_url)
        items = payload.get("items") if isinstance(payload, dict) else []
        if not isinstance(items, list):
            return []

        tenders: list[dict] = []
        seen: set[str] = set()
        for item in items:
            if not isinstance(item, dict):
                continue
            text = _compact_ws(
                " ".join(
                    str(item.get(key) or "")
                    for key in ("descriptionEnglish", "tenderRefNo", "issuedBy")
                )
            )
            if not text or not _contains_keyword_phrase(text, keyword):
                continue

            tender_id = item.get("tenderId")
            portal_url = self.portal.url
            if tender_id:
                documents = _fetch_canara_documents(str(tender_id))
                if documents:
                    portal_url = urljoin(self.portal.url, documents[0])

            ref_number = _compact_ws(str(item.get("tenderRefNo") or "")) or _extract_reference(
                text, portal_url
            )
            if ref_number.casefold() in seen:
                continue
            seen.add(ref_number.casefold())

            tenders.append(
                self.build_record(
                    ref_number=ref_number,
                    title=_compact_ws(str(item.get("descriptionEnglish") or ref_number)),
                    organisation=_compact_ws(str(item.get("issuedBy") or self.portal.organisation)),
                    state=self.portal.state,
                    portal_source=self.portal.source,
                    deadline_raw=str(item.get("lastDate") or ""),
                    value_raw="",
                    portal_url=portal_url,
                    keyword_hit=keyword,
                    tender_id=str(tender_id or "") or None,
                    link_verified=bool(portal_url),
                )
            )
        return tenders

    def _fetch_central_table(self, keyword: str) -> list[dict]:
        html = _fetch_html(self.portal.url)
        soup = BeautifulSoup(html, "lxml")
        tenders: list[dict] = []
        seen: set[str] = set()
        for row in soup.select("table tbody tr"):
            ref_cell = row.select_one("td.views-field-title")
            title_cell = row.select_one("td.views-field-body")
            deadline_cell = row.select_one("td.views-field-field-date-of-submission")
            doc_link = row.select_one("td.views-field-view a[href]")
            if ref_cell is None or title_cell is None:
                continue
            ref_number = _compact_ws(ref_cell.get_text(" ", strip=True))
            title = _compact_ws(title_cell.get_text(" ", strip=True))
            text = _compact_ws(" ".join(filter(None, [ref_number, title])))
            if not text or not _contains_keyword_phrase(text, keyword):
                continue
            if not doc_link:
                continue
            portal_url = urljoin(self.portal.url, str(doc_link.get("href") or "").strip())
            if ref_number.casefold() in seen:
                continue
            seen.add(ref_number.casefold())
            tenders.append(
                self.build_record(
                    ref_number=ref_number or _extract_reference(text, portal_url),
                    title=title or ref_number,
                    organisation=self.portal.organisation,
                    state=self.portal.state,
                    portal_source=self.portal.source,
                    deadline_raw=_compact_ws(deadline_cell.get_text(" ", strip=True)) if deadline_cell else "",
                    value_raw="",
                    portal_url=portal_url,
                    keyword_hit=keyword,
                    tender_id=None,
                    link_verified=True,
                )
            )
        return tenders


def _fetch_html(url: str) -> str:
    cached = HTML_CACHE.get(url)
    now = time.time()
    if cached and now - cached[0] < HTML_CACHE_TTL_SECONDS:
        return cached[1]

    headers = {
        **REQUEST_HEADERS,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-IN,en;q=0.9",
    }
    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
        response = client.get(url)
        response.raise_for_status()
        html = response.text
    HTML_CACHE[url] = (now, html)
    return html


def _fetch_json(url: str) -> dict[str, Any]:
    headers = {
        **REQUEST_HEADERS,
        "Accept": "application/json",
    }
    with httpx.Client(timeout=30, follow_redirects=True, headers=headers) as client:
        response = client.get(url)
        response.raise_for_status()
        data = response.json()
    return data if isinstance(data, dict) else {}


def _fetch_canara_documents(tender_id: str) -> list[str]:
    url = (
        "https://www.canarabank.bank.in/o/c/tenderdocuments/"
        f"?filter=tendersId%20eq%20{quote(tender_id)}"
    )
    payload = _fetch_json(url)
    items = payload.get("items") if isinstance(payload, dict) else []
    if not isinstance(items, list):
        return []
    links: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        file_entry = item.get("fileEntryEnglish")
        href = None
        if isinstance(file_entry, dict):
            link = file_entry.get("link")
            if isinstance(link, dict):
                href = link.get("href")
        if href:
            links.append(str(href))
    return links


def _candidate_containers(soup: BeautifulSoup) -> list[Tag]:
    seen: set[int] = set()
    containers: list[Tag] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if not _is_actionable_link(href):
            continue
        container = _best_container(anchor)
        if container is None:
            continue
        marker = id(container)
        if marker in seen:
            continue
        seen.add(marker)
        containers.append(container)
    return containers


def _best_container(anchor: Tag) -> Tag | None:
    fallback: Tag | None = None
    for ancestor in anchor.parents:
        if not isinstance(ancestor, Tag):
            continue
        if ancestor.name not in {"tr", "li", "article", "section", "div"}:
            continue
        text = _compact_ws(ancestor.get_text(" ", strip=True))
        if len(text) < 40:
            continue
        if len(text) <= 1200:
            return ancestor
        if fallback is None:
            fallback = ancestor
    parent = anchor.parent
    if fallback is not None:
        return fallback
    return parent if isinstance(parent, Tag) else None


def _container_links(container: Tag, base_url: str) -> list[str]:
    links: list[str] = []
    seen: set[str] = set()
    for anchor in container.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if not _is_actionable_link(href):
            continue
        absolute = urljoin(base_url, href)
        normalized = absolute.strip()
        if not normalized or normalized.casefold() in seen:
            continue
        seen.add(normalized.casefold())
        links.append(normalized)
    return links


def _is_actionable_link(href: str) -> bool:
    if not href or href.startswith(("javascript:", "#", "mailto:", "tel:")):
        return False
    if DOC_LINK_RE.search(href):
        return True
    parsed = urlparse(href)
    if parsed.scheme and parsed.netloc:
        return True
    lowered = href.casefold()
    return any(
        token in lowered
        for token in ("tender", "gem/", "download", "corrigendum", "notice", "rfp")
    )


def _choose_best_link(links: Iterable[str]) -> str:
    def priority(url: str) -> tuple[int, int]:
        lowered = url.casefold()
        if "gem/" in lowered or "bidplus.gem.gov.in" in lowered:
            return (0, len(url))
        if "downloadprocess.aspx" in lowered:
            return (1, len(url))
        if DOC_LINK_RE.search(lowered):
            return (2, len(url))
        return (3, len(url))

    return sorted(links, key=priority)[0]


def _extract_title(container: Tag, text: str, organisation: str) -> str:
    for selector in ("h1", "h2", "h3", "h4", "strong", "b"):
        heading = container.find(selector)
        if heading is None:
            continue
        candidate = _clean_title(heading.get_text(" ", strip=True))
        if _looks_like_title(candidate, organisation):
            return candidate

    for line in _visible_lines(container):
        candidate = _clean_title(line)
        if _looks_like_title(candidate, organisation):
            return candidate

    return _clean_title(text[:220])


def _visible_lines(container: Tag) -> list[str]:
    lines: list[str] = []
    for chunk in container.get_text("\n", strip=True).splitlines():
        text = _compact_ws(chunk)
        if text:
            lines.append(text)
    return lines


def _clean_title(value: str) -> str:
    cleaned = _compact_ws(value).strip(" -|:")
    cleaned = TITLE_NOISE_RE.sub(" ", cleaned)
    return _compact_ws(cleaned)


def _looks_like_title(value: str, organisation: str) -> bool:
    if len(value) < 12:
        return False
    normalized = value.casefold()
    if normalized == organisation.casefold():
        return False
    if "last date" in normalized or "submission" in normalized:
        return False
    return True


def _extract_deadline(text: str) -> str:
    match = DATE_LINE_RE.search(text)
    if match:
        return _compact_ws(match.group(1))
    return ""


def _extract_reference(text: str, portal_url: str) -> str:
    parsed = urlparse(portal_url)
    last_part = parsed.path.rstrip("/").rsplit("/", 1)[-1]
    if last_part and "." in last_part:
        return last_part.upper()

    for pattern in REF_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        candidate = (
            match.group(match.lastindex) if match.lastindex else match.group(0)
        ).strip().upper()
        if candidate in REFERENCE_STOPWORDS:
            continue
        if pattern is REF_PATTERNS[1] and not re.search(r"[\d/_-]", candidate):
            continue
        return candidate

    digest = hashlib.sha1(f"{portal_url}|{text[:120]}".encode("utf-8")).hexdigest()[:12]
    return f"BANK-{digest.upper()}"


def _extract_lic_reference(
    title: str, region: str, department: str, listed_date: str
) -> str:
    gem_match = re.search(r"\bGEM/\d{4}/B/\d+\b", title, flags=re.IGNORECASE)
    if gem_match:
        return gem_match.group(0).upper()

    tender_match = re.search(
        r"\b(?:LICI?|LIC)[A-Z0-9/._-]{4,}\b|\b[A-Z]{2,}/[A-Z0-9/._-]{4,}\b",
        title,
        flags=re.IGNORECASE,
    )
    if tender_match:
        return tender_match.group(0).upper()

    digest = hashlib.sha1(
        "|".join([region, department, title, listed_date]).encode("utf-8")
    ).hexdigest()[:12]
    return f"LIC-{digest.upper()}"


def _extract_lic_onclick_link(row: Tag) -> str | None:
    for element in row.find_all(attrs={"onclick": True}):
        onclick = str(element.get("onclick") or "")
        match = re.search(r"redirectLink\(\s*['\"]([^'\"]+)['\"]\s*\)", onclick)
        if match:
            return match.group(1).strip()
    return None


def _compact_ws(text: str) -> str:
    return " ".join((text or "").split())


def _contains_keyword_phrase(text: str, keyword: str) -> bool:
    normalized = " ".join(text.casefold().split())
    if not normalized:
        return False
    for term in _keyword_variants(keyword):
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


def scrape_pnb(keyword: str) -> list[dict]:
    return BankPortalFetcher(BANK_PORTALS["PNB Tenders"]).fetch(keyword)


def scrape_canara_bank(keyword: str) -> list[dict]:
    return BankPortalFetcher(BANK_PORTALS["Canara Bank Tenders"]).fetch(keyword)


def scrape_central_bank(keyword: str) -> list[dict]:
    return BankPortalFetcher(BANK_PORTALS["Central Bank of India Tenders"]).fetch(
        keyword
    )


def scrape_bank_of_india(keyword: str) -> list[dict]:
    return BankPortalFetcher(BANK_PORTALS["Bank of India Tenders"]).fetch(keyword)


def scrape_indian_bank(keyword: str) -> list[dict]:
    return BankPortalFetcher(BANK_PORTALS["Indian Bank Tenders"]).fetch(keyword)


def scrape_uco_bank(keyword: str) -> list[dict]:
    return BankPortalFetcher(BANK_PORTALS["UCO Bank Tenders"]).fetch(keyword)


def scrape_iob(keyword: str) -> list[dict]:
    return BankPortalFetcher(BANK_PORTALS["Indian Overseas Bank Tenders"]).fetch(
        keyword
    )


def scrape_lic(keyword: str) -> list[dict]:
    return BankPortalFetcher(BANK_PORTALS["LIC Tenders"]).fetch(keyword)
