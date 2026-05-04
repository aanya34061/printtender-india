import httpx
import pytest
import respx

from app.fetchers.aggregators import (
    scrape_bidassist,
    scrape_eprocure_search,
    scrape_tenderdekho,
    scrape_tendertiger,
)
from app.fetchers.base import RESULT_KEYS


@pytest.fixture(autouse=True)
def no_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.fetchers.base.time.sleep", lambda _seconds: None)


def assert_result_keys(tender: dict) -> None:
    assert tuple(tender.keys()) == RESULT_KEYS


@respx.mock
def test_scrape_bidassist_extracts_detail_link() -> None:
    html = """
    <div class="tender-card">
      <h2><a href="/rajasthan-printing/detail-12345678-1234-1234-1234-123456789abc">
        Rajasthan Medical Education Society Tender - Rajasthan Tender
      </a></h2>
      <p>Details: Tender for supply of stationery and printing services.</p>
      <p>Sawai Madhopur, Rajasthan</p>
      <p>Closing Date 30 Mar 2026</p>
      <p>Tender Amount₹ 7 Lac</p>
    </div>
    """
    respx.get(url__regex=r"https://bidassist\.com/printing-tender/active.*").mock(
        return_value=httpx.Response(200, text=html)
    )

    tenders = scrape_bidassist("printing")

    assert len(tenders) == 1
    assert_result_keys(tenders[0])
    assert tenders[0]["portal_source"] == "BidAssist"
    assert "/detail-" in tenders[0]["portal_url"]
    assert tenders[0]["link_type"] == "direct"


@respx.mock
def test_scrape_tenderdekho_extracts_slug_link() -> None:
    html = """
    <article>
      <a href="/tender/printing-forms-bhopal">MP Printing Forms Tender</a>
      <span>Organization: MPBSE</span>
      <span>Bhopal, Madhya Pradesh</span>
      <span>Bid End Date 12 Jun 2026</span>
    </article>
    """
    respx.get(url__regex=r"https://tenderdekho\.com/tenders.*").mock(
        return_value=httpx.Response(200, text=html)
    )

    tenders = scrape_tenderdekho("printing")

    assert len(tenders) == 1
    assert_result_keys(tenders[0])
    assert tenders[0]["portal_source"] == "TenderDekho"
    assert tenders[0]["tender_id"] == "printing-forms-bhopal"
    assert tenders[0]["portal_url"].endswith("/tender/printing-forms-bhopal")


@respx.mock
def test_scrape_tendertiger_extracts_detail_link() -> None:
    html = """
    <tr>
      <td><a href="/Tenderdetailbrief.aspx?SrNo=123456">Printing Tender</a></td>
      <td>Ref No: TT-PRINT-001</td>
      <td>Directorate of Printing</td>
      <td>Madhya Pradesh</td>
      <td>Due Date 20 Jun 2026</td>
    </tr>
    """
    respx.get(url__regex=r"https://global\.tendertiger\.com/quicksearch\.aspx.*").mock(
        return_value=httpx.Response(200, text=html)
    )

    tenders = scrape_tendertiger("printing")

    assert len(tenders) == 1
    assert_result_keys(tenders[0])
    assert tenders[0]["portal_source"] == "TenderTiger"
    assert "Tenderdetailbrief.aspx" in tenders[0]["portal_url"]


@respx.mock
def test_scrape_eprocure_search_extracts_sp_direct_link() -> None:
    html = """
    <table class="list_table">
      <tr>
        <td>1</td>
        <td>CPPP-PRINT-001</td>
        <td>Printing of annual reports</td>
        <td>Directorate of Printing</td>
        <td>30 Jun 2026</td>
        <td>₹ 5 Lac</td>
        <td><a href="/eprocure/app?component=%24DirectLink&page=FrontEndTendersByNIT&service=direct&sp=S12345678">View</a></td>
      </tr>
    </table>
    """
    respx.get(url__regex=r"https://eprocure\.gov\.in/eprocure/app.*").mock(
        return_value=httpx.Response(200, text=html)
    )

    tenders = scrape_eprocure_search("printing")

    assert len(tenders) == 1
    assert_result_keys(tenders[0])
    assert tenders[0]["portal_source"] == "CPPP"
    assert "sp=S12345678" in tenders[0]["portal_url"]
