# Run: playwright install chromium --with-deps before first use
import asyncio
import random
import re
from urllib.parse import quote_plus, urljoin

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from app.fetchers.base import BaseFetcher, USER_AGENT
from app.fetchers.deeplinks import build_deep_link, is_document_download_link

GEM_GENERIC_TEXT_RE = re.compile(
    r"^(?:view(?: details)?|details|bid details|bid document|document|download|apply|open|more|"
    r"corrigendum|boq|ra details?|seller details?)$",
    flags=re.IGNORECASE,
)

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
            return asyncio.run(self._fetch_async(keyword))
        except Exception as exc:
            self.log_result(self.portal_source, keyword, 0, 0, "error", str(exc))
            return []

    async def _fetch_async(self, keyword: str) -> list[dict]:
        tenders: list[dict] = []
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                context = await browser.new_context(user_agent=USER_AGENT)
                page = await context.new_page()
                await asyncio.sleep(random.uniform(2, 4))
                await page.goto(
                    f"{self.url}?search_bid={quote_plus(keyword)}",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
                if not await self._wait_for_results(page):
                    self.log_result(self.portal_source, keyword, 0, 0, "success")
                    return []
                tenders = await self._extract_results(page, keyword)
                self.log_result(
                    self.portal_source, keyword, len(tenders), len(tenders), "success"
                )
                return tenders
            finally:
                await browser.close()

    async def _wait_for_results(self, page) -> bool:
        try:
            await page.wait_for_selector(", ".join(self.selectors), timeout=15000)
            return True
        except PlaywrightTimeoutError:
            return False

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
        match = re.search(r"\bGEM/\d{4}/B/\d+\b", text, flags=re.IGNORECASE)
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
    if GEM_GENERIC_TEXT_RE.fullmatch(normalized):
        return True
    return _looks_like_field_value(normalized)


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
