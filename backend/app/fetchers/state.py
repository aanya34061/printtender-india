from dataclasses import dataclass

import httpx
from bs4 import BeautifulSoup

from app.fetchers.base import BaseFetcher, RawTender


@dataclass(frozen=True)
class StatePortal:
    source_name: str
    state: str
    url: str


STATE_PORTALS = [
    StatePortal("mp_tenders", "Madhya Pradesh", "https://mptenders.gov.in/nicgep/app"),
    StatePortal("up_tenders", "Uttar Pradesh", "https://etender.up.nic.in/nicgep/app"),
    StatePortal("maharashtra_tenders", "Maharashtra", "https://mahatenders.gov.in/nicgep/app"),
    StatePortal("rajasthan_sppp", "Rajasthan", "https://sppp.rajasthan.gov.in"),
    StatePortal("tenderdekho", "India", "https://tenderdekho.com"),
]


class StatePortalFetcher(BaseFetcher):
    def __init__(self, portal: StatePortal, keywords: list[str] | None = None) -> None:
        super().__init__(keywords=keywords)
        self.portal = portal
        self.source_name = portal.source_name

    async def fetch(self) -> list[RawTender]:
        tenders: list[RawTender] = []
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for keyword in self.keywords:
                await self.delay()
                response = await client.get(self.portal.url, params={"keyword": keyword})
                response.raise_for_status()
                tenders.extend(self.parse_html(response.text, keyword))
        return tenders

    def parse_html(self, html: str, keyword: str | None = None) -> list[RawTender]:
        soup = BeautifulSoup(html, "lxml")
        rows = soup.select("tr, .tender, .result, .bid-card")
        parsed: list[RawTender] = []
        for index, row in enumerate(rows):
            text = " ".join(row.get_text(" ", strip=True).split())
            matches = self.match_keywords(text)
            if keyword and keyword not in matches:
                matches.append(keyword)
            if not matches:
                continue
            link = row.find("a", href=True)
            external_id = row.get("data-id") or (link.get_text(strip=True) if link else text[:80]) or f"{self.source_name}-{index}"
            parsed.append(
                RawTender(
                    source=self.source_name,
                    external_id=external_id,
                    title=text[:500],
                    state=self.portal.state,
                    tender_url=link["href"] if link else None,
                    keywords=sorted(set(matches)),
                    raw_payload={"text": text},
                )
            )
        return parsed
