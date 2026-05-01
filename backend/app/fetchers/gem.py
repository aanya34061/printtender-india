from playwright.async_api import async_playwright

from app.fetchers.base import BaseFetcher, RawTender


class GeMFetcher(BaseFetcher):
    source_name = "gem"
    search_url = "https://bidplus.gem.gov.in/all-bids"

    async def fetch(self) -> list[RawTender]:
        tenders: list[RawTender] = []
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page()
            for keyword in self.keywords:
                await self.delay()
                await page.goto(self.search_url, wait_until="networkidle", timeout=60000)
                await page.fill("input[type='search'], input[name='search']", keyword)
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(2500)
                tenders.extend(await self._parse_cards(page, keyword))
            await browser.close()
        return tenders

    async def _parse_cards(self, page, keyword: str) -> list[RawTender]:
        cards = await page.locator(".card, .bid-card, .bid-result").all()
        parsed: list[RawTender] = []
        for index, card in enumerate(cards):
            text = (await card.inner_text()).strip()
            matches = self.match_keywords(text)
            if keyword not in matches:
                matches.append(keyword)
            title = text.splitlines()[0] if text else keyword
            parsed.append(
                RawTender(
                    source=self.source_name,
                    external_id=f"gem-{keyword}-{index}-{abs(hash(text))}",
                    title=title,
                    keywords=sorted(set(matches)),
                    raw_payload={"text": text},
                )
            )
        return parsed
