from collections import Counter
from datetime import datetime, timezone

import pytest

from app.sources import PORTAL_SOURCES
from app.tasks import fetch_job


def test_portal_scrapers_cover_active_portal_sources() -> None:
    assert {label for label, _scraper, _keywords in fetch_job.PORTAL_SCRAPERS} == set(
        PORTAL_SOURCES
    )


def test_mp_tenders_uses_image_product_keywords() -> None:
    keywords_by_source = {
        label: keywords
        for label, _scraper, keywords in fetch_job.PORTAL_SCRAPERS
    }

    assert keywords_by_source["MP Tenders"] is fetch_job.IMAGE_PRODUCT_KEYWORDS


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
                ["calendars", "diary"] if label == "MP Tenders" else ["printing"],
            )
            for label in PORTAL_SOURCES
        ),
    )
    monkeypatch.setattr(fetch_job, "_log_fetch", fake_log_fetch)
    monkeypatch.setattr(fetch_job, "normalise_tender", lambda raw: raw)
    monkeypatch.setattr(fetch_job, "deduplicate_tenders", lambda tenders: tenders)
    monkeypatch.setattr(fetch_job, "_upsert_tenders", fake_upsert)
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
    expected_calls = [
        (label, "printing") for label in PORTAL_SOURCES if label != "MP Tenders"
    ]
    expected_calls.extend(
        [("MP Tenders", "calendars"), ("MP Tenders", "diary")]
    )
    assert Counter(calls) == Counter(expected_calls)
    assert {row["portal_source"] for row in upserted} == set(PORTAL_SOURCES)
