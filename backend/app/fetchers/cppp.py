import xml.etree.ElementTree as ET
from html.entities import html5
import re

import httpx
from lxml import etree

from app.fetchers.base import BaseFetcher, REQUEST_HEADERS
from app.fetchers.aggregators import scrape_eprocure_search
from app.fetchers.deeplinks import (
    build_deep_link,
    extract_nic_tender_id,
    is_generic_homepage_url,
)


class CPPPFetcher(BaseFetcher):
    portal_source = "CPPP"
    url = "https://eprocure.gov.in/eprocure/app"

    def fetch(self, keyword: str) -> list[dict]:
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
                response = client.get(self.url, params=params)
                response.raise_for_status()
            tenders = self.parse_xml(response.text, keyword)
            if not tenders and self._requires_form_search(response.text):
                tenders = scrape_eprocure_search(keyword)
            self.log_result(
                self.portal_source, keyword, len(tenders), len(tenders), "success"
            )
            return tenders
        except Exception as exc:
            self.log_result(self.portal_source, keyword, 0, 0, "error", str(exc))
            return []

    def parse_xml(self, xml_text: str, keyword: str) -> list[dict]:
        try:
            sanitized = _sanitize_xml_entities(xml_text)
            root = etree.fromstring(
                sanitized.encode("utf-8"),
                parser=etree.XMLParser(recover=True),
            )
        except (ET.ParseError, etree.XMLSyntaxError, ValueError) as exc:
            self.log_result(
                self.portal_source, keyword, 0, 0, "error", f"XML parse failed: {exc}"
            )
            return []

        tenders: list[dict] = []
        for node in root.iter():
            fields = {
                self._tag_name(child.tag): (child.text or "").strip()
                for child in list(node)
            }
            if "TenderRefNo" not in fields and "TenderTitle" not in fields:
                continue

            title = fields.get("TenderTitle", "")
            ref_number = fields.get("TenderRefNo", "")
            if not title and not ref_number:
                continue

            # Extract the direct tender URL from the XML field
            raw_url = (
                fields.get("TenderUrl")
                or fields.get("TenderURL")
                or fields.get("Url")
                or ""
            ).strip()

            # Extract internal NIC tender ID from the URL (sp=SXXXXXXXX)
            tender_id = (
                extract_nic_tender_id(raw_url)
                or fields.get("NitId")
                or fields.get("TenderId")
            )

            # Use the XML URL only if it's a real deep link
            if (
                raw_url
                and "eprocure.gov.in" in raw_url
                and not is_generic_homepage_url(raw_url)
            ):
                portal_url = raw_url
                link_verified = True
            else:
                portal_url = build_deep_link(self.portal_source, ref_number, tender_id)
                link_verified = False

            tenders.append(
                self.build_record(
                    ref_number=ref_number,
                    title=title,
                    organisation=fields.get("OrganisationName"),
                    state=fields.get("State"),
                    portal_source=self.portal_source,
                    deadline_raw=fields.get("BidEndDate"),
                    value_raw=fields.get("TenderValue"),
                    portal_url=portal_url,
                    keyword_hit=keyword,
                    tender_id=tender_id,
                    link_verified=link_verified,
                )
            )
        return tenders

    @staticmethod
    def _tag_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]

    @staticmethod
    def _requires_form_search(text: str) -> bool:
        compact = " ".join(text.split()).casefold()
        return (
            compact.startswith("<html")
            and "your session in the client area has expired" in compact
        )


ENTITY_RE = re.compile(r"&([A-Za-z][A-Za-z0-9]+);")


def _sanitize_xml_entities(xml_text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        if name in {"amp", "lt", "gt", "apos", "quot"}:
            return match.group(0)
        value = html5.get(f"{name};")
        if value is None:
            return match.group(0)
        return value

    return ENTITY_RE.sub(replace, xml_text)


MP_FILTER_TERMS = (
    "madhya pradesh",
    "m.p.",
    "bhopal",
    "indore",
    "jabalpur",
    "gwalior",
)


def scrape_cppp_mp(keyword: str) -> list[dict]:
    """Fetch CPPP tenders constrained to Madhya Pradesh and printing keywords."""
    fetcher = CPPPFetcher()
    param_sets = [
        {
            "page": "FrontEndTendersByKeyword",
            "service": "page",
            "keyword": keyword,
            "searchBy": "0",
            "searchDateType": "TD",
            "state": "Madhya Pradesh",
            "statecode": "23",
        },
        {
            "page": "FrontEndTendersByKeyword",
            "service": "page",
            "keyword": keyword,
            "searchBy": "0",
            "searchDateType": "TD",
            "state": "MP",
        },
    ]
    tenders: list[dict] = []
    seen: set[str] = set()
    for params in param_sets:
        try:
            fetcher.wait_between_requests()
            with httpx.Client(
                timeout=30, follow_redirects=True, headers=REQUEST_HEADERS
            ) as client:
                response = client.get(fetcher.url, params=params)
                response.raise_for_status()
            for tender in fetcher.parse_xml(response.text, keyword):
                if not _is_madhya_pradesh_cppp_record(tender):
                    continue
                ref_number = tender.get("ref_number", "").strip().casefold()
                if not ref_number or ref_number in seen:
                    continue
                seen.add(ref_number)
                tender["state"] = "Madhya Pradesh"
                tender["portal_source"] = "CPPP"
                tenders.append(tender)
        except Exception as exc:
            fetcher.log_result("CPPP MP", keyword, 0, 0, "error", str(exc))
    fetcher.log_result("CPPP MP", keyword, len(tenders), len(tenders), "success")
    return tenders


def _is_madhya_pradesh_cppp_record(tender: dict) -> bool:
    text = " ".join(
        str(tender.get(key) or "")
        for key in ("state", "organisation", "title", "ref_number")
    )
    normalized = f" {text.casefold()} "
    if any(term in normalized for term in MP_FILTER_TERMS):
        return True
    return re.search(r"\bMP\b", text, flags=re.IGNORECASE) is not None


def main() -> None:
    for tender in CPPPFetcher().fetch_all_keywords():
        print(tender)


if __name__ == "__main__":
    main()
