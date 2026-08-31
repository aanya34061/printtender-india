from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
import respx

from app.fetchers.base import RESULT_KEYS
from app.fetchers.banks import (
    HTML_CACHE,
    scrape_bank_of_india,
    scrape_canara_bank,
    scrape_central_bank,
    scrape_indian_bank,
    scrape_lic,
    scrape_pnb,
    scrape_uco_bank,
)
from app.fetchers.cppp import CPPPFetcher
from app.fetchers.gem import (
    GeMFetcher,
    _pick_best_gem_href,
    _pick_gem_primary_candidate,
    _pick_gem_title_from_candidates,
    _prefer_gem_navigation_link,
)
from app.fetchers.mp_portals import (
    MPTENDERS_URL,
    _contains_keyword_phrase,
    scrape_mp_tenders,
)
from app.fetchers.state import StateFetcher
from app.keywords import IMAGE_PRODUCT_KEYWORDS


FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def no_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.fetchers.base.time.sleep", lambda _seconds: None)
    HTML_CACHE.clear()


def assert_result_keys(tender: dict) -> None:
    assert tuple(tender.keys()) == RESULT_KEYS


@respx.mock
def test_cppp_fetch_returns_three_dicts_with_expected_keys() -> None:
    xml = (FIXTURES / "cppp_sample.xml").read_text()
    respx.get(url__regex=r"https://eprocure\.gov\.in/eprocure/app.*").mock(
        return_value=httpx.Response(200, text=xml)
    )

    tenders = CPPPFetcher().fetch("printing")

    assert len(tenders) == 3
    assert all(isinstance(tender, dict) for tender in tenders)
    assert all_result_keys(tenders)
    assert tenders[0]["ref_number"] == "CPPP-PRINT-001"
    assert tenders[0]["portal_source"] == "CPPP"
    assert tenders[0]["keyword_hit"] == "printing"


def test_cppp_parse_xml_recovers_named_html_entities() -> None:
    xml = """
    <Resp>
      <Tender>
        <TenderRefNo>CPPP-ENT-001</TenderRefNo>
        <TenderTitle>Printing &amp; supply of calendars&nbsp;for schools</TenderTitle>
        <OrganisationName>Directorate of Printing</OrganisationName>
        <BidEndDate>30-Jun-2026</BidEndDate>
      </Tender>
    </Resp>
    """

    tenders = CPPPFetcher().parse_xml(xml, "calendars")

    assert len(tenders) == 1
    assert tenders[0]["title"] == "Printing & supply of calendars\xa0for schools"


@respx.mock
def test_state_fetch_returns_three_dicts_with_expected_keys() -> None:
    html = (FIXTURES / "state_sample.html").read_text()
    respx.get(url__regex=r"https://mptenders\.gov\.in/nicgep/app.*").mock(
        return_value=httpx.Response(200, text=html)
    )

    tenders = StateFetcher().fetch("printing", "MP")

    assert len(tenders) == 3
    assert all_result_keys(tenders)
    assert tenders[0]["ref_number"] == "MP-PRINT-001"
    assert tenders[0]["state"] == "Madhya Pradesh"
    assert tenders[0]["portal_source"] == "State-MP"
    assert tenders[0]["portal_url"].startswith("https://mptenders.gov.in/")


@respx.mock
def test_mp_tenders_fetches_image_keyword_from_nic_portal_via_keyword_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.fetchers.mp_portals.time.sleep", lambda _seconds: None)
    html = """
    <table>
      <tr>
        <td>1</td>
        <td>01-May-2026 10:00 AM</td>
        <td>30-Jun-2026 05:30 PM</td>
        <td>01-Jul-2026 11:00 AM</td>
        <td>Supply and printing of calendars</td>
        <td>Directorate of Printing</td>
      </tr>
      <tr>
        <td>2.</td>
        <td>01-May-2026 10:00 AM</td>
        <td>30-Jun-2026 05:30 PM</td>
        <td>01-Jul-2026 11:00 AM</td>
        <td>
          <a href="/nicgep/app?component=%24DirectLink_0&page=FrontEndAdvancedSearchResult&service=direct&session=T&sp=S12345678">
            [Supply and printing of calendars]
          </a>
          [MP-CAL-001][2026_DOP_1]
        </td>
        <td>Directorate of Printing</td>
      </tr>
    </table>
    """
    route = respx.get(url__regex=r"https://mptenders\.gov\.in/nicgep/app.*").mock(
        return_value=httpx.Response(200, text=html)
    )

    tenders = scrape_mp_tenders("calendars")

    assert route.called
    params = parse_qs(route.calls[0].request.url.query.decode())
    assert params["keyword"] == ["calendars"]
    assert params["page"] == ["FrontEndTendersByKeyword"]
    assert len(tenders) == 1
    assert_result_keys(tenders[0])
    assert tenders[0]["portal_source"] == "MP Tenders"
    assert tenders[0]["ref_number"] == "MP-CAL-001"
    assert tenders[0]["portal_url"].startswith(MPTENDERS_URL)
    assert "calendars" in IMAGE_PRODUCT_KEYWORDS


@respx.mock
def test_mp_tenders_falls_back_to_legacy_form_when_keyword_page_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.fetchers.mp_portals.time.sleep", lambda _seconds: None)
    home = """
    <form method="post" action="/nicgep/app" id="tenderSearch">
      <input type="hidden" name="component" value="$WebHomeBorder.$WebTenderSearch.tenderSearch" />
      <input type="hidden" name="page" value="Home" />
      <input type="hidden" name="service" value="direct" />
      <input type="hidden" name="session" value="T" />
      <input type="text" name="SearchDescription" value="" />
      <input type="submit" name="Go" value="Go" />
    </form>
    """
    html = """
    <table>
      <tr>
        <td>2.</td>
        <td>01-May-2026 10:00 AM</td>
        <td>30-Jun-2026 05:30 PM</td>
        <td>01-Jul-2026 11:00 AM</td>
        <td>
          <a href="/nicgep/app?component=%24DirectLink_0&page=FrontEndAdvancedSearchResult&service=direct&session=T&sp=S12345678">
            [Supply and printing of calendars]
          </a>
          [MP-CAL-001][2026_DOP_1]
        </td>
        <td>Directorate of Printing</td>
      </tr>
    </table>
    """
    keyword_route = respx.get(
        url__regex=r"https://mptenders\.gov\.in/nicgep/app\?.*keyword=.*"
    ).mock(
        return_value=httpx.Response(200, text="<html><body>No tenders found</body></html>")
    )
    respx.get("https://mptenders.gov.in/nicgep/app").mock(
        return_value=httpx.Response(200, text=home)
    )
    post_route = respx.post("https://mptenders.gov.in/nicgep/app").mock(
        return_value=httpx.Response(200, text=html)
    )

    tenders = scrape_mp_tenders("calendars")

    assert keyword_route.called
    assert post_route.called
    posted = parse_qs(post_route.calls[0].request.content.decode())
    assert posted["SearchDescription"] == ["calendars"]
    assert len(tenders) == 1


@respx.mock
def test_mp_tenders_ignores_legacy_page_chrome_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.fetchers.mp_portals.time.sleep", lambda _seconds: None)
    home = """
    <form method="post" action="/nicgep/app" id="tenderSearch">
      <input type="hidden" name="component" value="$WebHomeBorder.$WebTenderSearch.tenderSearch" />
      <input type="hidden" name="page" value="Home" />
      <input type="hidden" name="service" value="direct" />
      <input type="hidden" name="session" value="T" />
      <input type="text" name="SearchDescription" value="" />
      <input type="submit" name="Go" value="Go" />
    </form>
    """
    chrome_only_html = """
    <table>
      <tr><td>Search</td><td>Active Tenders</td></tr>
      <tr><td>Back</td><td>Back</td></tr>
      <tr><td>List</td><td>Tender List :</td></tr>
      <tr>
        <td>e-Published Date</td>
        <td>Closing Date</td>
        <td>Opening Date</td>
        <td>Title and Ref.No./Tender ID</td>
        <td>Organisation Chain</td>
      </tr>
    </table>
    """
    respx.get(
        url__regex=r"https://mptenders\.gov\.in/nicgep/app\?.*keyword=.*"
    ).mock(return_value=httpx.Response(200, text="<html><body>No tenders found</body></html>"))
    respx.get("https://mptenders.gov.in/nicgep/app").mock(
        return_value=httpx.Response(200, text=home)
    )
    respx.post("https://mptenders.gov.in/nicgep/app").mock(
        return_value=httpx.Response(200, text=chrome_only_html)
    )

    tenders = scrape_mp_tenders("calendars")

    assert tenders == []


@respx.mock
def test_mp_tenders_rebuilds_brittle_advanced_search_links() -> None:
    html = """
    <table>
      <tr>
        <td>2.</td>
        <td>01-May-2026 10:00 AM</td>
        <td>30-Jun-2026 05:30 PM</td>
        <td>01-Jul-2026 11:00 AM</td>
        <td>
          <a href="/nicgep/app?component=%24DirectLink_0&page=FrontEndAdvancedSearchResult&service=direct&session=T&sp=SWp8FvorQMqWExhnmC">
            [Supply and printing of calendars]
          </a>
          [MP-CAL-001][2026_DOP_1]
        </td>
        <td>Directorate of Printing</td>
      </tr>
    </table>
    """
    respx.get(url__regex=r"https://mptenders\.gov\.in/nicgep/app.*").mock(
        return_value=httpx.Response(200, text=html)
    )

    tenders = scrape_mp_tenders("calendars")

    assert len(tenders) == 1
    assert tenders[0]["tender_id"] == "2026_DOP_1"
    assert "FrontEndTendersByKeyword" in tenders[0]["portal_url"]
    assert "keyword=2026_DOP_1" in tenders[0]["portal_url"]
    assert "SWp8FvorQMqWExhnmC" not in tenders[0]["portal_url"]


@respx.mock
def test_state_fetcher_rebuilds_brittle_advanced_search_links() -> None:
    html = """
    <table class="list_table">
      <tr>
        <td>1.</td>
        <td>01-May-2026 10:00 AM</td>
        <td>30-Jun-2026 05:30 PM</td>
        <td>01-Jul-2026 11:00 AM</td>
        <td>
          <a href="/nicgep/app?component=%24DirectLink_0&page=FrontEndAdvancedSearchResult&service=direct&session=T&sp=SWp8FvorQMqWExhnmC">
            [Supply and printing of calendars]
          </a>
          [MH-CAL-001][2026_DOP_1]
        </td>
        <td>Directorate of Printing</td>
      </tr>
    </table>
    """
    respx.get(url__regex=r"https://mahatenders\.gov\.in/nicgep/app.*").mock(
        return_value=httpx.Response(200, text=html)
    )

    tenders = StateFetcher(keywords=["calendars"]).fetch("calendars", "MH")

    assert len(tenders) == 1
    assert tenders[0]["tender_id"] == "2026_DOP_1"
    assert "FrontEndTendersByKeyword" in tenders[0]["portal_url"]
    assert "keyword=2026_DOP_1" in tenders[0]["portal_url"]
    assert "SWp8FvorQMqWExhnmC" not in tenders[0]["portal_url"]


@respx.mock
def test_gem_fetcher_uses_official_json_data_and_direct_document_link() -> None:
    page = """<script>$.ajax({data: {'csrf_bd_gem_nk': 'token-123'}});</script>"""
    respx.get("https://bidplus.gem.gov.in/all-bids").mock(
        return_value=httpx.Response(200, text=page)
    )
    data_route = respx.post("https://bidplus.gem.gov.in/all-bids-data").mock(
        return_value=httpx.Response(
            200,
            json={
                "code": 200,
                "response": {
                    "response": {
                        "docs": [
                            {
                                "b_id": [9420823],
                                "b_bid_number": ["GEM/2026/B/7621949"],
                                "b_category_name": ["Printing of Log Sheets"],
                                "ba_official_details_deptName": [
                                    "Energy Department Uttar Pradesh"
                                ],
                                "final_end_date_sort": [
                                    "2026-07-19T15:00:00Z"
                                ],
                            }
                        ]
                    }
                },
            },
        )
    )

    tenders = GeMFetcher().fetch("printing")

    assert len(tenders) == 1
    assert tenders[0]["ref_number"] == "GEM/2026/B/7621949"
    assert tenders[0]["tender_id"] == "9420823"
    assert tenders[0]["portal_url"] == (
        "https://bidplus.gem.gov.in/showbidDocument/9420823"
    )
    request_payload = data_route.calls[0].request.content.decode()
    assert "printing" in request_payload


def test_mp_tenders_keyword_match_avoids_substring_false_positive() -> None:
    assert _contains_keyword_phrase("Work of Form Printing", "forms") is False
    assert _contains_keyword_phrase("Work of Forms Printing", "forms") is True
    assert _contains_keyword_phrase("Repairing of platforms", "forms") is False
    assert _contains_keyword_phrase("Supply of note books", "note books") is True


def test_gem_title_prefers_visible_heading_over_generic_link_text() -> None:
    raw_text = "\n".join(
        [
            "Bid Document",
            "Customised wall calendars for district offices",
            "Ministry: Department of Revenue",
            "End Date: 30 Jun 2026",
        ]
    )
    title = _pick_gem_title_from_candidates(
        raw_text,
        " ".join(raw_text.split()),
        ["Bid Document", "Customised wall calendars for district offices"],
    )

    assert title == "Customised wall calendars for district offices"


def test_gem_title_falls_back_to_first_meaningful_visible_line() -> None:
    raw_text = "\n".join(
        [
            "View Details",
            "Supply of answer books for examination",
            "Bid Number: GEM/2026/B/1234567",
            "Department: School Education",
        ]
    )
    title = _pick_gem_title_from_candidates(
        raw_text,
        " ".join(raw_text.split()),
        ["View Details"],
    )

    assert title == "Supply of answer books for examination"


def test_gem_href_prefers_bid_details_over_document_download() -> None:
    href = _pick_best_gem_href(
        [
            "/showbidDocument/9217773",
            "/bidding/bid-details/7393670",
        ]
    )

    assert href == "/bidding/bid-details/7393670"


def test_gem_href_falls_back_to_document_when_bid_details_missing() -> None:
    href = _pick_best_gem_href(
        [
            "/showbidDocument/9217773",
            "/some-other-link",
        ]
    )

    assert href == "/showbidDocument/9217773"


def test_gem_primary_candidate_keeps_title_and_href_together() -> None:
    title, href = _pick_gem_primary_candidate(
        "Bid Document Customised wall calendars for district offices",
        "Bid Document Customised wall calendars for district offices",
        [
            ("Bid Document", "/showbidDocument/9217773"),
            (
                "Customised wall calendars for district offices",
                "/bidding/bid-details/7393670",
            ),
        ],
    )

    assert title == "Customised wall calendars for district offices"
    assert href == "/bidding/bid-details/7393670"


def test_gem_prefers_navigation_link_over_document_download() -> None:
    href = _prefer_gem_navigation_link(
        "/showbidDocument/9217773",
        "/bidding/bid-details/7393670",
    )

    assert href == "/bidding/bid-details/7393670"


@respx.mock
def test_delay_is_called_between_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    xml = (FIXTURES / "cppp_sample.xml").read_text()
    route = respx.get(url__regex=r"https://eprocure\.gov\.in/eprocure/app.*").mock(
        return_value=httpx.Response(200, text=xml)
    )
    uniform_calls: list[tuple[int, int]] = []
    sleep_calls: list[float] = []

    def fake_uniform(start: int, end: int) -> float:
        uniform_calls.append((start, end))
        return 2.5

    monkeypatch.setattr("app.fetchers.base.random.uniform", fake_uniform)
    monkeypatch.setattr(
        "app.fetchers.base.time.sleep", lambda seconds: sleep_calls.append(seconds)
    )

    tenders = CPPPFetcher(keywords=["printing", "book printing"]).fetch_all_keywords()

    assert len(tenders) == 6
    assert route.call_count == 2
    assert uniform_calls == [(2, 4), (2, 4)]
    assert sleep_calls == [2.5, 2.5]


@respx.mock
def test_fetch_returns_empty_list_on_network_error() -> None:
    respx.get(url__regex=r"https://eprocure\.gov\.in/eprocure/app.*").mock(
        side_effect=httpx.ConnectError("boom")
    )

    assert CPPPFetcher().fetch("printing") == []


@respx.mock
def test_pnb_bank_fetcher_only_returns_keyword_matching_tenders() -> None:
    html = """
    <div class="tender-card">
      <h3>Tender for printing and supply of stationery registers</h3>
      <p>Last date of submission of Tender : 29-11-2026</p>
      <a href="/uploads/tenders/pnb-printing-registers.pdf">Download tender</a>
    </div>
    <div class="tender-card">
      <h3>Hiring of housekeeping services</h3>
      <p>Last date of submission of Tender : 01-12-2026</p>
      <a href="/uploads/tenders/pnb-housekeeping.pdf">Download tender</a>
    </div>
    """
    respx.get("https://pnb.bank.in/Tender.aspx").mock(
        return_value=httpx.Response(200, text=html)
    )

    tenders = scrape_pnb("registers")

    assert len(tenders) == 1
    assert_result_keys(tenders[0])
    assert tenders[0]["portal_source"] == "PNB Tenders"
    assert tenders[0]["ref_number"] == "PNB-PRINTING-REGISTERS.PDF"
    assert tenders[0]["portal_url"] == "https://pnb.bank.in/uploads/tenders/pnb-printing-registers.pdf"


@respx.mock
def test_indian_bank_fetcher_prefers_gem_link_and_extracts_ref() -> None:
    html = """
    <section class="entry">
      <h2>Indian Bank invites tender through GeM Portal for Printing and Supply of Diary, Calendars and Planners for the year 2026</h2>
      <p>Last date of submission of Tender : 2026-11-29</p>
      <a href="https://bidplus.gem.gov.in/all-bids?search_bid=GEM%2F2026%2FB%2F1234567">GEM/2026/B/1234567</a>
      <a href="/wp-content/uploads/2026/11/diary-calendars.pdf">Tender document</a>
    </section>
    """
    respx.get("https://indianbank.bank.in/HI/tender/").mock(
        return_value=httpx.Response(200, text=html)
    )

    tenders = scrape_indian_bank("calendars")

    assert len(tenders) == 1
    assert_result_keys(tenders[0])
    assert tenders[0]["portal_source"] == "Indian Bank Tenders"
    assert tenders[0]["ref_number"] == "GEM/2026/B/1234567"
    assert tenders[0]["portal_url"].startswith("https://bidplus.gem.gov.in/all-bids")


@respx.mock
def test_uco_bank_fetcher_deduplicates_multiple_links_in_same_tender_block() -> None:
    html = """
    <div class="tender-item">
      <strong>Tender for printing of annual report and brochures</strong>
      <span>Closing Date: 15/08/2026</span>
      <a href="/docs/uco-annual-report.pdf">Notice</a>
      <a href="/docs/uco-annual-report-annexure.pdf">Annexure</a>
    </div>
    """
    respx.get("https://www.uco.bank.in/en/tenders").mock(
        return_value=httpx.Response(200, text=html)
    )

    tenders = scrape_uco_bank("brochures")

    assert len(tenders) == 1
    assert_result_keys(tenders[0])
    assert tenders[0]["portal_source"] == "UCO Bank Tenders"
    assert tenders[0]["portal_url"] == "https://www.uco.bank.in/docs/uco-annual-report.pdf"


@respx.mock
def test_canara_bank_fetcher_uses_json_api_and_documents_endpoint() -> None:
    respx.get(
        url__regex=r"https://www\.canarabank\.bank\.in/o/c/tendersmasters/.*"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "tenderId": 42,
                        "tenderRefNo": "CB/PRINT/42",
                        "descriptionEnglish": "Printing and supply of desk calendars",
                        "issuedBy": "Marketing Division",
                        "lastDate": "2026-06-30T00:00:00Z",
                    }
                ]
            },
        )
    )
    respx.get(
        "https://www.canarabank.bank.in/o/c/tenderdocuments/?filter=tendersId%20eq%2042"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "fileEntryEnglish": {
                            "link": {
                                "href": "https://www.canarabank.bank.in/documents/d/guest/cb-calendar.pdf"
                            }
                        }
                    }
                ]
            },
        )
    )

    tenders = scrape_canara_bank("calendars")

    assert len(tenders) == 1
    assert_result_keys(tenders[0])
    assert tenders[0]["portal_source"] == "Canara Bank Tenders"
    assert tenders[0]["ref_number"] == "CB/PRINT/42"
    assert tenders[0]["portal_url"] == "https://www.canarabank.bank.in/documents/d/guest/cb-calendar.pdf"


@respx.mock
def test_central_bank_fetcher_reads_table_rows() -> None:
    html = """
    <table>
      <tbody>
        <tr>
          <td class="views-field views-field-title">CBOI/PRINT/2026</td>
          <td class="views-field views-field-body"><p>Printing and supply of paper stationery and calendars</p></td>
          <td class="views-field views-field-field-date-of-submission"><time>2026-06-05</time></td>
          <td class="views-field views-field-view"><a href="/sites/default/files/2026-05/print-calendar.pdf">View Documents</a></td>
        </tr>
      </tbody>
    </table>
    """
    respx.get("https://centralbank.bank.in/en/active-tender").mock(
        return_value=httpx.Response(200, text=html)
    )

    tenders = scrape_central_bank("calendars")

    assert len(tenders) == 1
    assert_result_keys(tenders[0])
    assert tenders[0]["portal_source"] == "Central Bank of India Tenders"
    assert tenders[0]["ref_number"] == "CBOI/PRINT/2026"
    assert tenders[0]["portal_url"] == "https://centralbank.bank.in/sites/default/files/2026-05/print-calendar.pdf"


@respx.mock
def test_bank_of_india_fetcher_reads_generic_tender_blocks() -> None:
    html = """
    <article>
      <h3>Tender for printing and supply of stationery forms</h3>
      <p>End Date: 30-Jun-2026</p>
      <a href="/documents/boi-stationery-forms.pdf">Download</a>
    </article>
    """
    respx.get("https://bankofindia.co.in/tenders").mock(
        return_value=httpx.Response(200, text=html)
    )

    tenders = scrape_bank_of_india("forms")

    assert len(tenders) == 1
    assert_result_keys(tenders[0])
    assert tenders[0]["portal_source"] == "Bank of India Tenders"
    assert tenders[0]["organisation"] == "Bank of India"
    assert tenders[0]["portal_url"] == "https://bankofindia.co.in/documents/boi-stationery-forms.pdf"


@respx.mock
def test_lic_fetcher_reads_current_tender_table_rows() -> None:
    html = """
    <table id="tableID">
      <tr>
        <th>Sort By Region</th>
        <th>Sort By Department</th>
        <th>Tender Description</th>
        <th>Date</th>
      </tr>
      <tr>
        <td>CO</td>
        <td>OS</td>
        <td>
          <a href="/documents/20121/0/lic-policy-bonds.pdf">
            Tender for centralized printing of policy bonds and dispatch for LIC of India
          </a>
        </td>
        <td>12/05/2026</td>
      </tr>
      <tr>
        <td>SZ</td>
        <td>Engg</td>
        <td>External painting works at branch office</td>
        <td>01/06/2026</td>
      </tr>
    </table>
    """
    respx.get("https://licindia.in/tenders").mock(
        return_value=httpx.Response(200, text=html)
    )

    tenders = scrape_lic("policy bonds")

    assert len(tenders) == 1
    assert_result_keys(tenders[0])
    assert tenders[0]["portal_source"] == "LIC Tenders"
    assert tenders[0]["title"] == (
        "Tender for centralized printing of policy bonds and dispatch for LIC of India"
    )
    assert tenders[0]["deadline_raw"] == ""
    assert tenders[0]["organisation"] == "Life Insurance Corporation of India - CO - OS"
    assert tenders[0]["portal_url"] == "https://licindia.in/documents/20121/0/lic-policy-bonds.pdf"


@respx.mock
def test_lic_fetcher_uses_active_table_and_redirect_links_only() -> None:
    html = """
    <table id="archiveTable">
      <tbody>
        <tr>
          <td>CO</td>
          <td>OS</td>
          <td>Expired stationery printing tender</td>
          <td>01/01/2025</td>
        </tr>
      </tbody>
    </table>
    <table id="tableID">
      <thead>
        <tr>
          <td>Sort By Region</td>
          <td>Sort By Department</td>
          <td>Tender Description</td>
          <td>Date</td>
        </tr>
      </thead>
      <tbody>
        <tr>
          <td>CO</td>
          <td>OS</td>
          <td onclick="redirectLink('/annual-contract-for-supply-of-stationery-book-items-enquiry-no.-stores/os/p-s/01-05/2026')">
            Annual contract for supply of stationery &amp; book items Enquiry No. Stores/OS/P&amp;S/01-05/2026
          </td>
          <td>27/05/2026</td>
        </tr>
      </tbody>
    </table>
    """
    respx.get("https://licindia.in/tenders").mock(
        return_value=httpx.Response(200, text=html)
    )

    tenders = scrape_lic("stationery")

    assert len(tenders) == 1
    assert tenders[0]["title"].startswith("Annual contract for supply of stationery")
    assert tenders[0]["deadline_raw"] == ""
    assert tenders[0]["portal_url"] == (
        "https://licindia.in/annual-contract-for-supply-of-stationery-book-items-enquiry-no.-stores/os/p-s/01-05/2026"
    )
    assert tenders[0]["link_verified"] is True


@respx.mock
def test_lic_fetcher_does_not_treat_archive_table_as_active() -> None:
    html = """
    <a href="/tenders/archive">Archive</a>
    <table id="archiveTable">
      <tbody>
        <tr>
          <td>CO</td>
          <td>OS</td>
          <td>Expired stationery printing tender</td>
          <td>01/01/2025</td>
        </tr>
      </tbody>
    </table>
    """
    respx.get("https://licindia.in/tenders").mock(
        return_value=httpx.Response(200, text=html)
    )

    tenders = scrape_lic("stationery")

    assert tenders == []


@respx.mock
def test_newspaper_scrapers_extract_printing_tenders_and_skip_non_printing() -> None:
    from app.fetchers.newspapers import (
        scrape_bhaskar,
        scrape_deshbandhu,
        scrape_freepressjournal,
        scrape_haribhoomi,
        scrape_swadesh,
        scrape_agniban,
        scrape_navswadesh,
        scrape_pradeshtoday,
        scrape_dabangdunia,
        scrape_peoplessamachar,
        scrape_rajexpress,
    )

    html = """
    <div>
      <div class="tender-box">
        <a href="/tenders/print-books-2026">निविदा सूचना: पुस्तकों एवं उत्तर पुस्तिकाओं का मुद्रण कार्य NIT-2026/01</a>
      </div>
      <div class="tender-box">
        <a href="/tenders/road-construction">निविदा: c.c. road construction work in ward 5</a>
      </div>
    </div>
    """
    respx.get(url__regex=r"https://.*").mock(return_value=httpx.Response(200, text=html))

    bhaskar_tenders = scrape_bhaskar("books")
    assert len(bhaskar_tenders) == 1
    assert bhaskar_tenders[0]["portal_source"] == "Dainik Bhaskar"
    assert "मुद्रण" in bhaskar_tenders[0]["title"] or "उत्तर पुस्तिका" in bhaskar_tenders[0]["title"]
    assert bhaskar_tenders[0]["state"] == "Madhya Pradesh"

    deshbandhu_tenders = scrape_deshbandhu("मुद्रण")
    assert len(deshbandhu_tenders) == 1
    assert deshbandhu_tenders[0]["portal_source"] == "Deshbandhu"

    fpj_tenders = scrape_freepressjournal("books")
    assert len(fpj_tenders) == 1
    assert fpj_tenders[0]["portal_source"] == "Free Press Journal"

    haribhoomi_tenders = scrape_haribhoomi("books")
    assert len(haribhoomi_tenders) == 1
    assert haribhoomi_tenders[0]["portal_source"] == "Hari Bhoomi"


def test_newspaper_sources_and_aliases() -> None:
    from app.sources import (
        NEWSPAPER_SOURCES,
        PORTAL_SOURCES,
        ACTIVE_TENDER_SOURCES,
        canonicalize_source,
        expand_source_filter,
        is_active_source,
    )

    expected_newspapers = [
        "Dainik Bhaskar",
        "Nai Dunia",
        "Patrika",
        "Dainik Jagran",
        "Nav Bharat",
        "Deshbandhu",
        "Raj Express",
        "Peoples Samachar",
        "Dabang Dunia",
        "Free Press Journal",
        "Pradesh Today",
        "Agniban",
        "Nav Swadesh",
        "Swadesh",
        "Hari Bhoomi",
    ]

    for np in expected_newspapers:
        assert np in NEWSPAPER_SOURCES
        assert np in ACTIVE_TENDER_SOURCES
        assert is_active_source(np) is True

    assert canonicalize_source("Naidunia") == "Nai Dunia"
    assert canonicalize_source("Rajasthan Patrika") == "Patrika"
    assert canonicalize_source("Navbharat") == "Nav Bharat"

    assert expand_source_filter("Naidunia") == ("Nai Dunia", "Naidunia")
    assert expand_source_filter("Rajasthan Patrika") == ("Patrika", "Rajasthan Patrika")
    assert expand_source_filter("Nav Bharat") == ("Nav Bharat", "Navbharat")


def all_result_keys(tenders: list[dict]) -> bool:
    for tender in tenders:
        assert_result_keys(tender)
    return True

