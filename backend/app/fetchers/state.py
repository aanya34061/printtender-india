from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.fetchers.base import BaseFetcher, REQUEST_HEADERS


STATE_PORTALS = {
    "MP": "https://mptenders.gov.in/nicgep/app",
    "UP": "https://etender.up.nic.in/nicgep/app",
    "MH": "https://mahatenders.gov.in/nicgep/app",
    "RJ": "https://sppp.rajasthan.gov.in/app",
}

STATE_NAMES = {
    "MP": "Madhya Pradesh",
    "UP": "Uttar Pradesh",
    "MH": "Maharashtra",
    "RJ": "Rajasthan",
}


@dataclass(frozen=True)
class StatePortal:
    state_code: str
    state: str
    url: str


class StateFetcher(BaseFetcher):
    def fetch(self, keyword: str, state: str = "MP") -> list[dict]:
        state_code = state.upper()
        portal_url = STATE_PORTALS.get(state_code)
        portal_source = f"State-{state_code}"
        if portal_url is None:
            self.log_result(
                portal_source, keyword, 0, 0, "error", f"Unsupported state: {state}"
            )
            return []

        params = {
            "page": "FrontEndTendersByKeyword",
            "service": "page",
            "keyword": keyword,
            "searchBy": "0",
            "searchDateType": "TD",
        }
        try:
            self.wait_between_requests()
            with httpx.Client(
                timeout=30, follow_redirects=True, headers=REQUEST_HEADERS
            ) as client:
                response = client.get(portal_url, params=params)
                response.raise_for_status()
            tenders = self.parse_html(response.text, keyword, state_code, portal_url)
            self.log_result(
                portal_source, keyword, len(tenders), len(tenders), "success"
            )
            return tenders
        except Exception as exc:
            self.log_result(portal_source, keyword, 0, 0, "error", str(exc))
            return []

    def fetch_all_states(self, keyword: str) -> list[dict]:
        tenders: list[dict] = []
        for state_code in STATE_PORTALS:
            tenders.extend(self.fetch(keyword, state_code))
        return tenders

    def fetch_all(self) -> list[dict]:
        tenders: list[dict] = []
        for keyword in self.keywords:
            tenders.extend(self.fetch_all_states(keyword))
        return tenders

    def parse_html(
        self, html: str, keyword: str, state_code: str, base_url: str
    ) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        tenders: list[dict] = []
        for row in soup.select("table.list_table > tr"):
            columns = row.find_all("td")
            if len(columns) < 6:
                continue

            ref_number = columns[1].get_text(" ", strip=True)
            title = columns[2].get_text(" ", strip=True)
            organisation = columns[3].get_text(" ", strip=True)
            deadline = columns[4].get_text(" ", strip=True)
            value = columns[5].get_text(" ", strip=True)
            link = row.find("a", href=True)

            if not ref_number and not title:
                continue

            tenders.append(
                self.build_record(
                    ref_number=ref_number,
                    title=title,
                    organisation=organisation,
                    state=STATE_NAMES.get(state_code, state_code),
                    portal_source=f"State-{state_code}",
                    deadline_raw=deadline,
                    value_raw=value,
                    portal_url=urljoin(base_url, link["href"]) if link else base_url,
                    keyword_hit=keyword,
                )
            )
        return tenders


class StatePortalFetcher(StateFetcher):
    def __init__(self, portal: StatePortal, keywords: list[str] | None = None) -> None:
        super().__init__(keywords=keywords)
        self.portal = portal

    def fetch(self, keyword: str | None = None, state: str | None = None) -> list[dict]:
        return super().fetch(
            keyword or self.keywords[0], state or self.portal.state_code
        )

    def parse_html(self, html: str, keyword: str | None = None) -> list[dict]:
        return super().parse_html(
            html, keyword or self.keywords[0], self.portal.state_code, self.portal.url
        )


def main() -> None:
    for tender in StateFetcher().fetch_all():
        print(tender)


if __name__ == "__main__":
    main()
