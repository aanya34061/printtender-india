# Run: playwright install chromium --with-deps before first use
import asyncio
import json
import random
import re
import threading
from typing import Any
from urllib.parse import urljoin

import httpx

from app.fetchers.base import BaseFetcher, REQUEST_HEADERS
from app.fetchers.deeplinks import build_deep_link, is_document_download_link

GEM_GENERIC_TEXT_RE = re.compile(
    r"^(?:view(?: details)?|details|bid details|bid document|document|download|apply|open|more|"
    r"corrigendum|boq|ra details?|seller details?|ra no(?::.*)?)$",
    flags=re.IGNORECASE,
)
GEM_REFERENCE_RE = re.compile(r"\bGEM/\d{4}/[A-Z]+/\d+\b", flags=re.IGNORECASE)

GEM_FIELD_LABELS = (
    "Bid Title",
    "Item",
    "Title",
    "Bid Number",
    "Ministry",
    "Department",
    "Organisation",
    "Organization",
    "End Date",
    "Bid End Date",
    "Closing Date",
    "Value",
    "Estimated Bid Value",
    "Bid Value",
)


class GeMFetcher(BaseFetcher):
    portal_source = "GeM"
    url = "https://bidplus.gem.gov.in/all-bids"
    selectors = (".bid-list-item", ".card", "table tr")

    def fetch(self, keyword: str) -> list[dict]:
        try:
            tenders = self._fetch_official_data(keyword)
            self.log_result(
                self.portal_source, keyword, len(tenders), len(tenders), "success"
            )
            return tenders
        except Exception as exc:
            self.log_result(self.portal_source, keyword, 0, 0, "error", str(exc))
            return []

    def _fetch_official_data(self, keyword: str) -> list[dict]:
        """Fetch GeM's public JSON data request used by the official bids page."""
        self.wait_between_requests()
        headers = {
            **REQUEST_HEADERS,
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Referer": self.url,
            "X-Requested-With": "XMLHttpRequest",
        }
        with httpx.Client(timeout=25, follow_redirects=True, headers=headers) as client:
            page = client.get(self.url)
            page.raise_for_status()
            csrf_match = re.search(
                r"csrf_bd_gem_nk['\"]?\s*:\s*['\"]([^'\"]+)",
                page.text,
            )
            if csrf_match is None:
                raise RuntimeError("GeM CSRF token not found")

            payload = {
                "param": {"searchBid": keyword, "searchType": "fullText"},
                "filter": {
                    "bidStatusType": "ongoing_bids",
                    "byType": "all",
                    "highBidValue": "",
                    "byEndDate": {"from": "", "to": ""},
                    "sort": "Bid-End-Date-Oldest",
                },
            }
            response = client.post(
                "https://bidplus.gem.gov.in/all-bids-data",
                data={
                    "payload": json.dumps(payload, separators=(",", ":")),
                    "csrf_bd_gem_nk": csrf_match.group(1),
                },
            )
            response.raise_for_status()
            body = response.json()

        if body.get("code") != 200:
            raise RuntimeError(f"GeM data request failed: {body.get('code')!r}")
        docs = body.get("response", {}).get("response", {}).get("docs", [])
        if not isinstance(docs, list):
            return []

        tenders: list[dict] = []
        seen: set[str] = set()
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            bid_number = _gem_text(doc.get("b_bid_number"))
            document_id = _gem_text(doc.get("b_id"))
            if not bid_number or not document_id or bid_number.casefold() in seen:
                continue
            seen.add(bid_number.casefold())

            categories = _gem_text(doc.get("b_category_name"))
            boq_title = _gem_text(doc.get("bbt_title"))
            title = _compact_ws(" - ".join(filter(None, (categories, boq_title))))
            if title:
                title = f"Procurement of {title}"
            title = _finalize_gem_title(title, bid_number, keyword)
            organisation = _compact_ws(
                " - ".join(
                    filter(
                        None,
                        (
                            _gem_text(doc.get("ba_official_details_minName")),
                            _gem_text(doc.get("ba_official_details_deptName")),
                        ),
                    )
                )
            )
            portal_url = f"https://bidplus.gem.gov.in/showbidDocument/{document_id}"
            tenders.append(
                self.build_record(
                    ref_number=bid_number,
                    title=title,
                    organisation=organisation,
                    state="India",
                    portal_source=self.portal_source,
                    deadline_raw=_gem_text(doc.get("final_end_date_sort")),
                    value_raw=_gem_text(
                        doc.get("b_bid_value") or doc.get("estimated_bid_value")
                    ),
                    portal_url=portal_url,
                    keyword_hit=keyword,
                    tender_id=document_id,
                    link_verified=True,
                )
            )
        return tenders

    async def _extract_results(self, page, keyword: str) -> list[dict]:
        locators = [
            page.locator(".bid-list-item"),
            page.locator(".card"),
            page.locator("table tr"),
        ]
        tenders: list[dict] = []
        seen: set[str] = set()
        for locator in locators:
            count = await locator.count()
            for index in range(count):
                item = locator.nth(index)
                direct_link = await self._first_bid_card_href(item)
                raw_text = await item.inner_text()
                text = _compact_ws(raw_text)
                if not text or text.casefold() in seen:
                    continue
                seen.add(text.casefold())

                extracted_bid_number = self._extract_bid_number(text)
                bid_number = extracted_bid_number or f"GeM-{keyword}-{index + 1}"
                title, linked_href = await _extract_gem_primary_candidate(
                    item, raw_text, text
                )
                title = _finalize_gem_title(title, bid_number, keyword)

                chosen_link = _prefer_gem_navigation_link(linked_href, direct_link)
                if chosen_link:
                    portal_url = (
                        chosen_link
                        if chosen_link.startswith("http")
                        else urljoin("https://bidplus.gem.gov.in", chosen_link)
                    )
                    link_verified = True
                    tender_id = self._document_id_from_url(portal_url) or bid_number
                else:
                    tender_id = extracted_bid_number
                    portal_url = build_deep_link(
                        self.portal_source, bid_number, tender_id
                    )
                    link_verified = False

                tenders.append(
                    self.build_record(
                        ref_number=bid_number,
                        title=title,
                        organisation=self._extract_field(
                            text,
                            ("Ministry", "Department", "Organisation", "Organization"),
                        ),
                        state="India",
                        portal_source=self.portal_source,
                        deadline_raw=self._extract_field(
                            text, ("End Date", "Bid End Date", "Closing Date")
                        ),
                        value_raw=self._extract_field(
                            text, ("Value", "Estimated Bid Value", "Bid Value")
                        ),
                        portal_url=portal_url,
                        keyword_hit=keyword,
                        tender_id=tender_id,
                        link_verified=link_verified,
                    )
                )
        return tenders

    async def _first_link(self, item) -> str | None:
        links = item.locator("a[href]")
        hrefs: list[str] = []
        count = await links.count()
        for index in range(min(count, 8)):
            href = await links.nth(index).get_attribute("href")
            if href:
                hrefs.append(href)
        return _pick_best_gem_href(hrefs)

    async def _first_bid_card_href(self, item) -> str | None:
        return await self._first_link(item)

    @staticmethod
    def _extract_bid_number(text: str) -> str | None:
        match = re.search(r"\bGEM/\d{4}/[A-Z]+/\d+\b", text, flags=re.IGNORECASE)
        return match.group(0) if match else None

    @staticmethod
    def _document_id_from_url(url: str) -> str | None:
        match = re.search(r"showbidDocument/([^?#]+)", url)
        return match.group(1) if match else None

    @staticmethod
    def _extract_field(text: str, labels: tuple[str, ...]) -> str | None:
        for label in labels:
            pattern = (
                rf"{re.escape(label)}\s*:?\s*(.+?)(?=\s+[A-Z][A-Za-z ]{{2,}}\s*:|\Z)"
            )
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()
        return None

    @staticmethod
    def _fallback_title(text: str) -> str:
        return text[:180]


def _compact_ws(text: str) -> str:
    return " ".join((text or "").split())


def _gem_text(value: Any) -> str:
    while isinstance(value, (list, tuple)):
        if not value:
            return ""
        value = value[0]
    if value is None:
        return ""
    return _compact_ws(str(value))


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


def _clean_gem_candidate(text: str) -> str:
    return _compact_ws(text).strip(" -|:")


def _looks_like_field_value(text: str) -> bool:
    normalized = _clean_gem_candidate(text)
    if not normalized:
        return False
    return any(
        normalized.casefold().startswith(f"{label.casefold()}:")
        or normalized.casefold() == label.casefold()
        for label in GEM_FIELD_LABELS
    )


def _is_generic_gem_text(text: str) -> bool:
    normalized = _clean_gem_candidate(text)
    if not normalized:
        return True
    if _is_gem_bid_number_text(normalized):
        return True
    if GEM_GENERIC_TEXT_RE.fullmatch(normalized):
        return True
    return _looks_like_field_value(normalized)


def _is_gem_bid_number_text(text: str) -> bool:
    normalized = _clean_gem_candidate(text)
    match = GEM_REFERENCE_RE.fullmatch(normalized)
    return match is not None


def _finalize_gem_title(title: str, bid_number: str, keyword: str) -> str:
    cleaned = _clean_gem_candidate(title)
    if not cleaned or _is_generic_gem_text(cleaned):
        return f"GeM tender for {keyword} - {bid_number}"
    return cleaned


def _pick_gem_title_from_candidates(
    raw_text: str, fallback_text: str, candidates: list[str]
) -> str:
    seen: set[str] = set()
    for candidate in candidates:
        cleaned = _clean_gem_candidate(candidate)
        key = cleaned.casefold()
        if key in seen or _is_generic_gem_text(cleaned):
            continue
        seen.add(key)
        if len(cleaned) >= 6:
            return cleaned

    for line in raw_text.splitlines():
        cleaned = _clean_gem_candidate(line)
        key = cleaned.casefold()
        if key in seen or _is_generic_gem_text(cleaned):
            continue
        seen.add(key)
        if len(cleaned) >= 6 and not GeMFetcher._extract_bid_number(cleaned):
            return cleaned

    return GeMFetcher._extract_field(fallback_text, ("Bid Title", "Item", "Title")) or GeMFetcher._fallback_title(fallback_text)


async def _extract_gem_title(item, raw_text: str, compact_text: str) -> str:
    title, _href = await _extract_gem_primary_candidate(item, raw_text, compact_text)
    return title


def _pick_gem_primary_candidate(
    raw_text: str,
    fallback_text: str,
    candidates: list[tuple[str, str | None]],
) -> tuple[str, str | None]:
    seen: set[str] = set()
    for text, href in candidates:
        cleaned = _clean_gem_candidate(text)
        key = cleaned.casefold()
        if key in seen or _is_generic_gem_text(cleaned):
            continue
        seen.add(key)
        if len(cleaned) >= 6:
            return cleaned, href
    return _pick_gem_title_from_candidates(raw_text, fallback_text, []), None


async def _extract_gem_primary_candidate(
    item, raw_text: str, compact_text: str
) -> tuple[str, str | None]:
    selectors = (
        ".bid-title",
        ".card-title",
        ".item-title",
        ".item-name",
        ".bid-name",
        "h1",
        "h2",
        "h3",
        "h4",
        "h5",
        "a[href*='bid-details']",
        "a[href*='showbidDocument']",
        "a[href]",
    )
    candidates: list[tuple[str, str | None]] = []
    for selector in selectors:
        locator = item.locator(selector)
        count = await locator.count()
        for index in range(min(count, 5)):
            node = locator.nth(index)
            value = await node.inner_text()
            href = await node.evaluate(
                """(el) => {
                    const anchor = el.closest('a[href]') || el.querySelector('a[href]');
                    return anchor ? anchor.getAttribute('href') : null;
                }"""
            )
            if value:
                candidates.append((value, href))
    return _pick_gem_primary_candidate(raw_text, compact_text, candidates)


def _pick_best_gem_href(hrefs: list[str]) -> str | None:
    cleaned = [href.strip() for href in hrefs if href and href.strip()]
    if not cleaned:
        return None

    for href in cleaned:
        lowered = href.casefold()
        if "bid-details" in lowered:
            return href
    for href in cleaned:
        lowered = href.casefold()
        if "showbiddocument" in lowered:
            return href
    return cleaned[0]


def _prefer_gem_navigation_link(
    linked_href: str | None, direct_href: str | None
) -> str | None:
    if linked_href and direct_href:
        linked_is_download = is_document_download_link(
            linked_href
            if linked_href.startswith("http")
            else urljoin("https://bidplus.gem.gov.in", linked_href)
        )
        direct_is_download = is_document_download_link(
            direct_href
            if direct_href.startswith("http")
            else urljoin("https://bidplus.gem.gov.in", direct_href)
        )
        if linked_is_download and not direct_is_download:
            return direct_href
    return linked_href or direct_href


def main() -> None:
    for tender in GeMFetcher().fetch_all_keywords():
        print(tender)


if __name__ == "__main__":
    main()
