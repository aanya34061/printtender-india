# Run: playwright install chromium --with-deps before first use
import asyncio
import random
import re
from urllib.parse import quote_plus, urljoin

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from app.fetchers.base import BaseFetcher, USER_AGENT
from app.fetchers.deeplinks import build_deep_link


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
                text = " ".join((await item.inner_text()).split())
                if not text or text.casefold() in seen:
                    continue
                seen.add(text.casefold())

                extracted_bid_number = self._extract_bid_number(text)
                bid_number = extracted_bid_number or f"GeM-{keyword}-{index + 1}"

                # Prefer a direct bid-details link from the card's anchor tags
                direct_link = await self._first_bid_details_link(item)
                if direct_link:
                    portal_url = (
                        direct_link
                        if direct_link.startswith("http")
                        else urljoin("https://bidplus.gem.gov.in", direct_link)
                    )
                    link_verified = True
                    # Derive tender_id from URL: .../bid-details/BID-2025-B-12345
                    tid_match = re.search(r"bid-details/(.+?)(?:\?|$)", portal_url)
                    tender_id = (
                        tid_match.group(1)
                        if tid_match
                        else bid_number.replace("/", "-")
                    )
                else:
                    tender_id = (
                        extracted_bid_number.replace("/", "-")
                        if extracted_bid_number
                        else None
                    )
                    portal_url = build_deep_link(
                        self.portal_source, bid_number, tender_id
                    )
                    link_verified = False

                tenders.append(
                    self.build_record(
                        ref_number=bid_number,
                        title=self._extract_field(text, ("Bid Title", "Item", "Title"))
                        or self._fallback_title(text),
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
        if await links.count() == 0:
            return None
        return await links.first.get_attribute("href")

    async def _first_bid_details_link(self, item) -> str | None:
        """Return the direct bid-details href if present on the card, else None."""
        # Prefer anchor with bid-details in the href
        bid_links = item.locator("a[href*='bid-details']")
        if await bid_links.count() > 0:
            return await bid_links.first.get_attribute("href")
        # Fallback: any anchor (caller will construct URL from bid number)
        return None

    @staticmethod
    def _extract_bid_number(text: str) -> str | None:
        match = re.search(r"\bGEM/\d{4}/B/\d+\b", text, flags=re.IGNORECASE)
        return match.group(0) if match else None

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


def main() -> None:
    for tender in GeMFetcher().fetch_all_keywords():
        print(tender)


if __name__ == "__main__":
    main()
