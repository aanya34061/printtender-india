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

BRACKETED_TENDER_RE = re.compile(
    r"^\[(?P<title>.*?)\]\s*\[(?P<ref>.*?)\]\[(?P<tender_id>.*?)\]\s*$"
)


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
                response = self._search_response(
                    client=client,
                    portal_url=portal_url,
                    keyword=keyword,
                    params=params,
                )
            tenders = self.parse_html(response.text, keyword, state_code, portal_url)
            self.log_result(
                portal_source, keyword, len(tenders), len(tenders), "success"
            )
            return tenders
        except Exception as exc:
            self.log_result(portal_source, keyword, 0, 0, "error", str(exc))
            return []

    def _search_response(
        self,
        *,
        client: httpx.Client,
        portal_url: str,
        keyword: str,
        params: dict[str, str],
    ) -> httpx.Response:
        response = client.get(portal_url, params=params)
        response.raise_for_status()
        if not self._requires_form_search(response.text):
            return response

        home = client.get(portal_url)
        home.raise_for_status()
        payload = self._extract_search_form(home.text)
        payload["SearchDescription"] = keyword
        payload["Go"] = payload.get("Go") or "Go"
        form_response = client.post(portal_url, data=payload)
        form_response.raise_for_status()
        return form_response

    def _requires_form_search(self, html: str) -> bool:
        compact = " ".join(html.split()).casefold()
        return (
            "your session in the client area has expired" in compact
            or "click here to re-login" in compact
        )

    def _extract_search_form(self, html: str) -> dict[str, str]:
        soup = BeautifulSoup(html, "lxml")
        form = soup.find("form", {"id": "tenderSearch"})
        if form is None:
            raise RuntimeError("State portal search form not found")
        return {
            str(field.get("name")): str(field.get("value") or "")
            for field in form.find_all("input")
            if field.get("name")
        }

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

            ref_number, title, organisation, deadline, value, parsed_tender_id = (
                self._parse_row(columns)
            )

            if not ref_number and not title:
                continue
            if (
                ref_number.casefold() == "e-published date"
                and title.casefold() == "closing date"
            ):
                continue

            portal_source = f"State-{state_code}"

            # Prefer a direct NIT/view link over generic links
            nit_tag = row.find("a", href=re.compile(r"FrontEndTendersByNIT|FrontEndViewTender|DirectLink|tenderRef"))
            if nit_tag:
                href = nit_tag.get("href", "")
                portal_url = urljoin(base_url, href) if not href.startswith("http") else href
                tender_id = extract_nic_tender_id(portal_url) or parsed_tender_id
                link_verified = True
            else:
                # Fallback: any <a> in the row
                any_link = row.find("a", href=True)
                if any_link:
                    href = any_link["href"]
                    portal_url = urljoin(base_url, href) if not href.startswith("http") else href
                    tender_id = extract_nic_tender_id(portal_url) or parsed_tender_id
                    link_verified = bool(tender_id)
                else:
                    tender_id = parsed_tender_id
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

    def _parse_row(
        self, columns: list
    ) -> tuple[str, str, str, str, str, str | None]:
        date_like_second = self._looks_like_datetime(columns[1].get_text(" ", strip=True))
        bracketed_title_ref = columns[4].get_text(" ", strip=True)
        if date_like_second and "[" in bracketed_title_ref and "]" in bracketed_title_ref:
            title, ref_number, tender_id = self._parse_bracketed_tender(bracketed_title_ref)
            return (
                ref_number,
                title,
                columns[5].get_text(" ", strip=True),
                columns[2].get_text(" ", strip=True),
                "",
                tender_id,
            )

        return (
            columns[1].get_text(" ", strip=True),
            columns[2].get_text(" ", strip=True),
            columns[3].get_text(" ", strip=True),
            columns[4].get_text(" ", strip=True),
            columns[5].get_text(" ", strip=True),
            None,
        )

    def _looks_like_datetime(self, text: str) -> bool:
        return (
            re.search(
                r"\b\d{1,2}[-/ ][A-Za-z]{3,9}[-/ ]\d{2,4}\b",
                text,
                flags=re.IGNORECASE,
            )
            is not None
        )

    def _parse_bracketed_tender(self, text: str) -> tuple[str, str, str | None]:
        compact = " ".join(text.split())
        match = BRACKETED_TENDER_RE.match(compact)
        if not match:
            return compact, compact, None
        return (
            match.group("title").strip(),
            match.group("ref").strip(),
            match.group("tender_id").strip() or None,
        )


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
