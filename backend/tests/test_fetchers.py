from pathlib import Path

from app.fetchers.cppp import CPPPFetcher
from app.fetchers.state import StatePortal, StatePortalFetcher


FIXTURES = Path(__file__).parent / "fixtures"


def test_cppp_parser_extracts_printing_tender() -> None:
    xml = (FIXTURES / "cppp_sample.xml").read_text()
    tenders = CPPPFetcher().parse_xml(xml)
    assert len(tenders) == 1
    assert tenders[0].external_id == "CPPP-PRINT-001"
    assert "offset printing" in tenders[0].keywords


def test_state_parser_extracts_printing_tender() -> None:
    html = (FIXTURES / "state_sample.html").read_text()
    portal = StatePortal("mp_tenders", "Madhya Pradesh", "https://mptenders.gov.in/nicgep/app")
    tenders = StatePortalFetcher(portal).parse_html(html)
    assert len(tenders) == 1
    assert tenders[0].state == "Madhya Pradesh"
    assert "calendar printing" in tenders[0].keywords
