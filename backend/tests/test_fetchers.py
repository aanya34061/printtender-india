from pathlib import Path

import httpx
import pytest
import respx

from app.fetchers.base import RESULT_KEYS
from app.fetchers.cppp import CPPPFetcher
from app.fetchers.state import StateFetcher


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
