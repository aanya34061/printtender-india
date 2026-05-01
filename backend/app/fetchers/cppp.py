import xml.etree.ElementTree as ET

import httpx

from app.fetchers.base import BaseFetcher, REQUEST_HEADERS


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
            self.log_result(
                self.portal_source, keyword, len(tenders), len(tenders), "success"
            )
            return tenders
        except Exception as exc:
            self.log_result(self.portal_source, keyword, 0, 0, "error", str(exc))
            return []

    def parse_xml(self, xml_text: str, keyword: str) -> list[dict]:
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as exc:
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

            tenders.append(
                self.build_record(
                    ref_number=ref_number,
                    title=title,
                    organisation=fields.get("OrganisationName"),
                    state=fields.get("State"),
                    portal_source=self.portal_source,
                    deadline_raw=fields.get("BidEndDate"),
                    value_raw=fields.get("TenderValue"),
                    portal_url=fields.get("TenderUrl"),
                    keyword_hit=keyword,
                )
            )
        return tenders

    @staticmethod
    def _tag_name(tag: str) -> str:
        return tag.rsplit("}", 1)[-1]


def main() -> None:
    for tender in CPPPFetcher().fetch_all_keywords():
        print(tender)


if __name__ == "__main__":
    main()
