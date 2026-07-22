from collections import Counter
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from app.sources import LIVE_PORTAL_SOURCES, PORTAL_SOURCES
from app.tasks import fetch_job
from app.tasks.mail_scheduler import IST, next_scheduled_mail_at


def test_portal_scrapers_cover_active_portal_sources() -> None:
    assert {label for label, _scraper, _keywords in fetch_job.PORTAL_SCRAPERS} == set(
        PORTAL_SOURCES
    )


def test_live_portal_sources_cover_all_portal_sources() -> None:
    assert set(LIVE_PORTAL_SOURCES) == set(PORTAL_SOURCES)


def test_limited_keyword_selection_prioritizes_high_signal_terms() -> None:
    selected = fetch_job._select_keywords(
        ["calendars", "diary", "printing", "stationery", "forms"],
        3,
    )

    assert selected == ["printing", "stationery", "forms"]


def test_portal_fetch_specs_start_with_one_keyword_per_source() -> None:
    specs = fetch_job._build_portal_fetch_specs(set(LIVE_PORTAL_SOURCES), 2)
    expected_first_round = [
        label for label, _scraper, _keywords in fetch_job.PORTAL_SCRAPERS
    ]
    first_round = [
        label for label, _scraper, _keyword in specs[: len(expected_first_round)]
    ]

    assert first_round == expected_first_round
    assert len(specs) == len(fetch_job.PORTAL_SCRAPERS) * 2


def test_mp_tenders_uses_mp_specific_keywords() -> None:
    keywords_by_source = {
        label: keywords for label, _scraper, keywords in fetch_job.PORTAL_SCRAPERS
    }

    assert keywords_by_source["MP Tenders"] is fetch_job.MP_TENDERS_KEYWORDS
    assert keywords_by_source["eproc.mp.gov.in"] is fetch_job.MP_TENDERS_KEYWORDS


def test_bank_portals_use_focused_bank_keywords() -> None:
    keywords_by_source = {
        label: keywords for label, _scraper, keywords in fetch_job.PORTAL_SCRAPERS
    }

    for label in (
        "PNB Tenders",
        "Canara Bank Tenders",
        "Central Bank of India Tenders",
        "Bank of India Tenders",
        "Indian Bank Tenders",
        "UCO Bank Tenders",
        "Indian Overseas Bank Tenders",
        "LIC Tenders",
    ):
        assert keywords_by_source[label] is fetch_job.BANK_TENDER_KEYWORDS


def test_alert_matching_uses_all_subscriber_keywords_and_tender_fields() -> None:
    subscriber = MagicMock()
    subscriber.keywords = ["printing", "stationery", "printing"]
    subscriber.keyword = "forms"
    tender = MagicMock()
    tender.title = "Annual office supply tender"
    tender.keywords = ["paper"]
    tender.organisation = "State Stationery Department"
    tender.category = "office supplies"

    keywords = fetch_job._subscriber_keywords(subscriber)

    assert keywords == ["printing", "stationery", "forms"]
    assert fetch_job._tender_matches_any_keyword(tender, keywords) is True


def test_alert_frequency_due_windows() -> None:
    now = datetime(2026, 6, 1, 12, tzinfo=timezone.utc)
    subscriber = MagicMock()

    subscriber.frequency = "instant"
    subscriber.last_alerted_at = now
    subscriber.last_sent = now
    assert fetch_job._subscriber_is_due(subscriber, now) is False
    subscriber.last_alerted_at = None
    subscriber.last_sent = None
    assert fetch_job._subscriber_is_due(subscriber, now) is True

    subscriber.frequency = "daily"
    subscriber.last_alerted_at = now - timedelta(hours=22)
    assert fetch_job._subscriber_is_due(subscriber, now) is False
    subscriber.last_alerted_at = now - timedelta(hours=24)
    assert fetch_job._subscriber_is_due(subscriber, now) is True

    subscriber.frequency = "weekly"
    subscriber.last_alerted_at = now - timedelta(days=6)
    assert fetch_job._subscriber_is_due(subscriber, now) is False
    subscriber.last_alerted_at = now - timedelta(days=7)
    assert fetch_job._subscriber_is_due(subscriber, now) is True


def test_next_scheduled_mail_at_uses_requested_ist_times() -> None:
    assert next_scheduled_mail_at(datetime(2026, 6, 2, 7, 59, tzinfo=IST)) == datetime(
        2026, 6, 2, 8, 0, tzinfo=IST
    )
    assert next_scheduled_mail_at(datetime(2026, 6, 2, 8, 1, tzinfo=IST)) == datetime(
        2026, 6, 3, 8, 0, tzinfo=IST
    )


@pytest.mark.asyncio
async def test_run_fetch_cycle_schedules_all_portal_scrapers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str]] = []
    upserted: list[dict] = []

    class FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 5, 12, 10, tzinfo=timezone.utc)

    def make_scraper(label: str):
        def scraper(keyword: str) -> list[dict]:
            calls.append((label, keyword))
            return [{"portal_source": label, "ref_number": f"{label}-{keyword}"}]

        return scraper

    async def fake_log_fetch(
        source: str, found: int, status: str, error: str | None = None
    ) -> None:
        return None

    async def fake_upsert(tenders: list[dict]) -> list[int]:
        upserted.extend(tenders)
        return []

    async def fake_deactivate_missing_source_tenders(
        _source: str, _active_ref_numbers: set[str]
    ) -> int:
        return 0

    async def fake_send_matching_alerts(_ids: list[int]) -> int:
        return 0

    monkeypatch.setattr(fetch_job, "PRINT_KEYWORDS", ["printing"])
    monkeypatch.setattr(fetch_job, "datetime", FixedDatetime)
    monkeypatch.setattr(
        fetch_job,
        "PORTAL_SCRAPERS",
        tuple(
            (
                label,
                make_scraper(label),
                ["printing"],
            )
            for label in PORTAL_SOURCES
        ),
    )
    monkeypatch.setattr(fetch_job, "_log_fetch", fake_log_fetch)
    monkeypatch.setattr(fetch_job, "normalise_tender", lambda raw: raw)
    monkeypatch.setattr(fetch_job, "deduplicate_tenders", lambda tenders: tenders)
    monkeypatch.setattr(fetch_job, "_upsert_tenders", fake_upsert)
    monkeypatch.setattr(
        fetch_job,
        "_deactivate_missing_source_tenders",
        fake_deactivate_missing_source_tenders,
    )
    monkeypatch.setattr(fetch_job, "send_matching_alerts", fake_send_matching_alerts)

    import app.fetchers.newspapers as newspapers

    for name in (
        "scrape_toi",
        "scrape_ht",
        "scrape_et",
        "scrape_thehindu",
        "scrape_bhaskar",
        "scrape_patrika",
        "scrape_naidunia",
        "scrape_navbharat",
        "scrape_jagran",
        "scrape_amarujala",
        "scrape_tendernotice",
        "scrape_indiatendernotice",
        "scrape_publicnotice",
    ):
        monkeypatch.setattr(newspapers, name, lambda _keyword: [])

    count = await fetch_job.run_fetch_cycle()

    assert count == 0
    expected_calls = [(label, "printing") for label in PORTAL_SOURCES]
    assert Counter(calls) == Counter(expected_calls)
    assert {row["portal_source"] for row in upserted} == set(PORTAL_SOURCES)


@pytest.mark.asyncio
async def test_run_fetch_cycle_deactivates_lic_rows_missing_from_active_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deactivated: list[tuple[str, set[str]]] = []

    def lic_scraper(keyword: str) -> list[dict]:
        return [
            {
                "portal_source": "LIC Tenders",
                "ref_number": f"LIC-ACTIVE-{keyword}",
                "title": f"Active LIC {keyword} printing tender",
                "organisation": "Life Insurance Corporation of India",
            }
        ]

    async def fake_log_fetch(
        source: str, found: int, status: str, error: str | None = None
    ) -> None:
        return None

    async def fake_upsert(_tenders: list[dict]) -> list[int]:
        return []

    async def fake_deactivate_missing_source_tenders(
        source: str, active_ref_numbers: set[str]
    ) -> int:
        deactivated.append((source, active_ref_numbers))
        return 2

    async def fake_send_matching_alerts(_ids: list[int]) -> int:
        return 0

    monkeypatch.setattr(
        fetch_job,
        "PORTAL_SCRAPERS",
        (("LIC Tenders", lic_scraper, ("stationery", "forms")),),
    )
    monkeypatch.setattr(fetch_job, "_log_fetch", fake_log_fetch)
    monkeypatch.setattr(fetch_job, "normalise_tender", lambda raw: raw)
    monkeypatch.setattr(fetch_job, "deduplicate_tenders", lambda tenders: tenders)
    monkeypatch.setattr(fetch_job, "_upsert_tenders", fake_upsert)
    monkeypatch.setattr(
        fetch_job,
        "_deactivate_missing_source_tenders",
        fake_deactivate_missing_source_tenders,
    )
    monkeypatch.setattr(fetch_job, "send_matching_alerts", fake_send_matching_alerts)

    await fetch_job.run_fetch_cycle(include_newspapers=False)

    assert deactivated == [
        (
            "LIC Tenders",
            {"LIC-ACTIVE-stationery", "LIC-ACTIVE-forms"},
        )
    ]


@pytest.mark.asyncio
async def test_run_fetch_cycle_preserves_rows_after_ambiguous_empty_refresh(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deactivated: list[tuple[str, set[str]]] = []

    def empty_scraper(_keyword: str) -> list[dict]:
        return []

    async def fake_log_fetch(
        source: str, found: int, status: str, error: str | None = None
    ) -> None:
        return None

    async def fake_upsert(_tenders: list[dict]) -> list[int]:
        return []

    async def fake_deactivate_missing_source_tenders(
        source: str, active_ref_numbers: set[str]
    ) -> int:
        deactivated.append((source, active_ref_numbers))
        return 3

    async def fake_send_matching_alerts(_ids: list[int]) -> int:
        return 0

    monkeypatch.setattr(
        fetch_job,
        "PORTAL_SCRAPERS",
        (("CPPP", empty_scraper, ("printing",)),),
    )
    monkeypatch.setattr(fetch_job, "_log_fetch", fake_log_fetch)
    monkeypatch.setattr(fetch_job, "normalise_tender", lambda raw: raw)
    monkeypatch.setattr(fetch_job, "deduplicate_tenders", lambda tenders: tenders)
    monkeypatch.setattr(fetch_job, "_upsert_tenders", fake_upsert)
    monkeypatch.setattr(
        fetch_job,
        "_deactivate_missing_source_tenders",
        fake_deactivate_missing_source_tenders,
    )
    monkeypatch.setattr(fetch_job, "send_matching_alerts", fake_send_matching_alerts)

    await fetch_job.run_fetch_cycle(include_newspapers=False)

    assert deactivated == []


@pytest.mark.asyncio
async def test_run_fetch_cycle_skips_deactivation_after_partial_source_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    deactivated: list[tuple[str, set[str]]] = []

    def flaky_scraper(keyword: str) -> list[dict]:
        if keyword == "forms":
            raise RuntimeError("portal timeout")
        return [
            {
                "portal_source": "GeM",
                "ref_number": "GEM-ACTIVE-1",
                "title": "Active GeM printing tender",
                "organisation": "Buyer",
            }
        ]

    async def fake_log_fetch(
        source: str, found: int, status: str, error: str | None = None
    ) -> None:
        return None

    async def fake_upsert(_tenders: list[dict]) -> list[int]:
        return []

    async def fake_deactivate_missing_source_tenders(
        source: str, active_ref_numbers: set[str]
    ) -> int:
        deactivated.append((source, active_ref_numbers))
        return 1

    async def fake_send_matching_alerts(_ids: list[int]) -> int:
        return 0

    monkeypatch.setattr(
        fetch_job,
        "PORTAL_SCRAPERS",
        (("GeM", flaky_scraper, ("printing", "forms")),),
    )
    monkeypatch.setattr(fetch_job, "_log_fetch", fake_log_fetch)
    monkeypatch.setattr(fetch_job, "normalise_tender", lambda raw: raw)
    monkeypatch.setattr(fetch_job, "deduplicate_tenders", lambda tenders: tenders)
    monkeypatch.setattr(fetch_job, "_upsert_tenders", fake_upsert)
    monkeypatch.setattr(
        fetch_job,
        "_deactivate_missing_source_tenders",
        fake_deactivate_missing_source_tenders,
    )
    monkeypatch.setattr(fetch_job, "send_matching_alerts", fake_send_matching_alerts)

    await fetch_job.run_fetch_cycle(include_newspapers=False)

    assert deactivated == []


@pytest.mark.asyncio
async def test_scheduled_subscriber_mails_sends_to_active_subscribers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subscriber = MagicMock()
    subscriber.id = 1
    subscriber.email = "press@example.com"
    subscriber.last_sent = None
    tender = MagicMock()
    commits = 0
    sent: list[tuple[str, list[MagicMock]]] = []

    class FakeSession:
        def __init__(self) -> None:
            self.calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def scalars(self, _query):
            self.calls += 1
            return [subscriber] if self.calls == 1 else [tender]

        async def commit(self):
            nonlocal commits
            commits += 1

    def fake_send(to_email: str, tenders: list[MagicMock]) -> bool:
        sent.append((to_email, tenders))
        return True

    async def fake_claim(_session, _email: str, _now: datetime) -> bool:
        return True

    monkeypatch.setattr(fetch_job, "async_session", FakeSession)
    monkeypatch.setattr(fetch_job, "send_all_categories_email", fake_send)
    monkeypatch.setattr(fetch_job, "_claim_scheduled_subscriber_mail", fake_claim)

    result = await fetch_job.send_scheduled_subscriber_mails()

    assert result == {"total_subscribers": 1, "sent": 1, "failed": []}
    assert sent == [("press@example.com", [tender])]
    assert commits == 0


@pytest.mark.asyncio
async def test_scheduled_subscriber_mails_sends_once_per_email(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first_subscriber = MagicMock()
    first_subscriber.id = 1
    first_subscriber.email = "press@example.com"
    second_subscriber = MagicMock()
    second_subscriber.id = 2
    second_subscriber.email = "press@example.com"
    tender = MagicMock()
    sent: list[str] = []
    claimed: list[str] = []

    class FakeSession:
        def __init__(self) -> None:
            self.calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def scalars(self, _query):
            self.calls += 1
            if self.calls == 1:
                return [first_subscriber, second_subscriber]
            return [tender]

    def fake_send(to_email: str, _tenders: list[MagicMock]) -> bool:
        sent.append(to_email)
        return True

    async def fake_claim(_session, email: str, _now: datetime) -> bool:
        claimed.append(email)
        return True

    monkeypatch.setattr(fetch_job, "async_session", FakeSession)
    monkeypatch.setattr(fetch_job, "send_all_categories_email", fake_send)
    monkeypatch.setattr(fetch_job, "_claim_scheduled_subscriber_mail", fake_claim)

    result = await fetch_job.send_scheduled_subscriber_mails()

    assert result == {"total_subscribers": 2, "sent": 1, "failed": []}
    assert claimed == ["press@example.com"]
    assert sent == ["press@example.com"]


@pytest.mark.asyncio
async def test_scheduled_subscriber_mails_skips_recently_sent_subscriber(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    subscriber = MagicMock()
    subscriber.id = 1
    subscriber.email = "press@example.com"
    subscriber.last_sent = datetime.now(timezone.utc) - timedelta(minutes=10)
    tender = MagicMock()
    commits = 0
    sent: list[str] = []

    class FakeSession:
        def __init__(self) -> None:
            self.calls = 0

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def scalars(self, _query):
            self.calls += 1
            return [subscriber] if self.calls == 1 else [tender]

        async def commit(self):
            nonlocal commits
            commits += 1

    def fake_send(to_email: str, _tenders: list[MagicMock]) -> bool:
        sent.append(to_email)
        return True

    async def fake_claim(_session, _email: str, _now: datetime) -> bool:
        return False

    monkeypatch.setattr(fetch_job, "async_session", FakeSession)
    monkeypatch.setattr(fetch_job, "send_all_categories_email", fake_send)
    monkeypatch.setattr(fetch_job, "_claim_scheduled_subscriber_mail", fake_claim)

    result = await fetch_job.send_scheduled_subscriber_mails()

    assert result == {"total_subscribers": 1, "sent": 0, "failed": []}
    assert sent == []
    assert commits == 0
