import httpx
from bs4 import BeautifulSoup

from app.fetchers.base import BaseFetcher, RawTender


class CPPPFetcher(BaseFetcher):
    source_name = "cppp"
    feed_url = "https://eprocure.gov.in/eprocure/app"

    async def fetch(self) -> list[RawTender]:
        tenders: list[RawTender] = []
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            for keyword in self.keywords:
                await self.delay()
                response = await client.get(self.feed_url, params={"component": "LatestActiveTenders", "keyword": keyword})
                response.raise_for_status()
                tenders.extend(self.parse_xml(response.text, keyword))
        return tenders

    def parse_xml(self, xml_text: str, keyword: str | None = None) -> list[RawTender]:
        soup = BeautifulSoup(xml_text, "xml")
        parsed: list[RawTender] = []
        for item in soup.find_all(["item", "tender"]):
            title = self._text(item, "title") or self._text(item, "TenderTitle") or ""
            matches = self.match_keywords(title)
            if keyword and keyword not in matches:
                matches.append(keyword)
            if not matches:
                continue
            external_id = self._text(item, "id") or self._text(item, "TenderID") or title
            parsed.append(
                RawTender(
                    source=self.source_name,
                    external_id=external_id.strip(),
                    title=title.strip(),
                    buyer=self._text(item, "OrganisationName"),
                    state=self._text(item, "State"),
                    deadline=self._text(item, "BidSubmissionClosingDate"),
                    published_at=self._text(item, "PublishedDate"),
                    tender_url=self._text(item, "link"),
                    keywords=sorted(set(matches)),
                    raw_payload={child.name: child.get_text(strip=True) for child in item.find_all() if child.name},
                )
            )
        return parsed

    @staticmethod
    def _text(item, tag: str) -> str | None:
        node = item.find(tag)
        return node.get_text(strip=True) if node else None
