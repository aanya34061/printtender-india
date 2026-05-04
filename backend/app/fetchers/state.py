import re
from dataclasses import dataclass
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.fetchers.base import BaseFetcher, REQUEST_HEADERS
from app.fetchers.deeplinks import build_deep_link, extract_nic_tender_id


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
        # Some state portals (e.g. Rajasthan) have self-signed SSL certs
        verify_ssl = state_code != "RJ"
        try:
            self.wait_between_requests()
            with httpx.Client(
                timeout=30, follow_redirects=True, headers=REQUEST_HEADERS, verify=verify_ssl
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

            if not ref_number and not title:
                continue

            portal_source = f"State-{state_code}"

            # Prefer a direct NIT/view link over generic links
            nit_tag = row.find("a", href=re.compile(r"FrontEndTendersByNIT|FrontEndViewTender|DirectLink|tenderRef"))
            if nit_tag:
                href = nit_tag.get("href", "")
                portal_url = urljoin(base_url, href) if not href.startswith("http") else href
                tender_id = extract_nic_tender_id(portal_url)
                link_verified = True
            else:
                # Fallback: any <a> in the row
                any_link = row.find("a", href=True)
                if any_link:
                    href = any_link["href"]
                    portal_url = urljoin(base_url, href) if not href.startswith("http") else href
                    tender_id = extract_nic_tender_id(portal_url)
                    link_verified = bool(tender_id)
                else:
                    tender_id = None
                    portal_url = build_deep_link(portal_source, ref_number, None)
                    link_verified = False

            tenders.append(
                self.build_record(
                    ref_number=ref_number,
                    title=title,
                    organisation=organisation,
                    state=STATE_NAMES.get(state_code, state_code),
                    portal_source=portal_source,
                    deadline_raw=deadline,
                    value_raw=value,
                    portal_url=portal_url,
                    keyword_hit=keyword,
                    tender_id=tender_id,
                    link_verified=link_verified,
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
