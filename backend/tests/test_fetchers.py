from pathlib import Path
from urllib.parse import parse_qs

import httpx
import pytest
import respx

from app.fetchers.base import RESULT_KEYS
from app.fetchers.cppp import CPPPFetcher
from app.fetchers.gem import (
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


def all_result_keys(tenders: list[dict]) -> bool:
    for tender in tenders:
        assert_result_keys(tender)
    return True
