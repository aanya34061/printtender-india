import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.database import async_session
from app.email_service import send_tender_alert_email
from app.fetchers.aggregators import scrape_bidassist, scrape_tenderdekho
from app.fetchers.cppp import CPPPFetcher
from app.fetchers.gem import GeMFetcher
from app.fetchers.mp_portals import (
    scrape_mp_forest,
    scrape_mp_info,
    scrape_mp_pwd,
    scrape_mp_tenders,
    scrape_mpbse,
)
from app.fetchers.state import StateFetcher
from app.keywords import IMAGE_PRODUCT_KEYWORDS, PRINT_KEYWORDS
from app.models import AlertSubscription, FetchLog, Tender
from app.processing.deduplicator import deduplicate_tenders
from app.processing.normaliser import normalise_tender
from app.sources import ACTIVE_TENDER_SOURCES
from app.tasks.celery_app import celery_app


def _scrape_cppp(keyword: str) -> list[dict]:
    return CPPPFetcher().fetch(keyword)


def _scrape_gem(keyword: str) -> list[dict]:
    return GeMFetcher().fetch(keyword)


def _scrape_state(state_code: str):
    def scraper(keyword: str) -> list[dict]:
        return StateFetcher().fetch(keyword, state_code)

    return scraper


PORTAL_SCRAPERS = (
    ("CPPP", _scrape_cppp, PRINT_KEYWORDS),
    ("GeM", _scrape_gem, PRINT_KEYWORDS),
    ("MP Tenders", scrape_mp_tenders, IMAGE_PRODUCT_KEYWORDS),
    ("MP PWD", scrape_mp_pwd, PRINT_KEYWORDS),
    ("MPBSE", scrape_mpbse, PRINT_KEYWORDS),
    ("MP Forest", scrape_mp_forest, PRINT_KEYWORDS),
    ("MP Info", scrape_mp_info, PRINT_KEYWORDS),
    ("State-MP", _scrape_state("MP"), PRINT_KEYWORDS),
    ("State-UP", _scrape_state("UP"), PRINT_KEYWORDS),
    ("Maharashtra Tenders", _scrape_state("MH"), PRINT_KEYWORDS),
    ("State-RJ", _scrape_state("RJ"), PRINT_KEYWORDS),
    ("TenderDekho", scrape_tenderdekho, PRINT_KEYWORDS),
    ("BidAssist", scrape_bidassist, PRINT_KEYWORDS),
)


async def _upsert_tenders(tenders: list) -> list[int]:
    new_ids: list[int] = []
    async with async_session() as session:
        ref_numbers = [tender.ref_number for tender in tenders]
        existing_refs: set[str] = set()
        if ref_numbers:
            result = await session.scalars(
                select(Tender.ref_number).where(Tender.ref_number.in_(ref_numbers))
            )
            existing_refs = set(result)
        for tender in tenders:
            stmt = (
                insert(Tender)
                .values(**tender.model_dump())
                .on_conflict_do_update(
                    index_elements=["ref_number"],
                    set_={
                        "title": tender.title,
                        "organisation": tender.organisation,
                        "bid_end_date": tender.bid_end_date,
                        "portal_url": tender.portal_url,
                        "tender_id": tender.tender_id,
                        "link_type": tender.link_type,
                        "link_verified": tender.link_verified,
                        "is_active": tender.is_active,
                        "fetched_at": datetime.now(timezone.utc),
                    },
                )
                .returning(Tender.id)
            )
            result = await session.execute(stmt)
            saved_id = result.scalar_one_or_none()
            if saved_id is not None and tender.ref_number not in existing_refs:
                new_ids.append(saved_id)
        await session.commit()
    return new_ids


async def _log_fetch(
    source: str, found: int, status: str, error: str | None = None
) -> None:
    async with async_session() as session:
        session.add(
            FetchLog(
                portal=source,
                fetched_at=datetime.now(timezone.utc),
                tenders_found=found,
                new_added=0,
                status=status,
                error_msg=error,
            )
        )
        await session.commit()


async def run_fetch_cycle() -> int:
    """
    Run fetch cycle across all sources. Parallelise IO-bound synchronous scrapers using
    asyncio.to_thread and run async scrapers concurrently where possible. Add timeouts
    and semaphores to prevent slow/hanging scrapers from blocking the whole cycle.
    """

    all_raw: list = []

    # limit concurrent thread-based scrapers
    sem_sync = asyncio.Semaphore(6)

    async def _run_sync_and_log(label: str, func, *args):
        try:
            async with sem_sync:
                if args:
                    raw = await asyncio.wait_for(
                        asyncio.to_thread(func, *args), timeout=30
                    )
                else:
                    raw = await asyncio.wait_for(
                        asyncio.to_thread(func), timeout=30
                    )
            await _log_fetch(label, len(raw), "ok")
            return label, raw
        except asyncio.TimeoutError:
            await _log_fetch(label, 0, "error", "timeout")
            return label, []
        except Exception as exc:
            await _log_fetch(label, 0, "error", str(exc))
            return label, []

    tasks = []

    for label, scraper, keywords in PORTAL_SCRAPERS:
        for keyword in keywords:
            tasks.append(
                asyncio.create_task(_run_sync_and_log(label, scraper, keyword))
            )

    # Newspaper/notice scrapers remain active without exposing source filters in the UI.
    from app.fetchers.newspapers import (
        scrape_toi,
        scrape_ht,
        scrape_et,
        scrape_thehindu,
        scrape_bhaskar,
        scrape_patrika,
        scrape_naidunia,
        scrape_navbharat,
        scrape_jagran,
        scrape_amarujala,
        scrape_tendernotice,
        scrape_indiatendernotice,
        scrape_publicnotice,
    )

    newspaper_scrapers = [
        ("TOI Tenders", scrape_toi),
        ("HT Tenders", scrape_ht),
        ("ET Tenders", scrape_et),
        ("The Hindu Tenders", scrape_thehindu),
        ("Dainik Bhaskar", scrape_bhaskar),
        ("Patrika", scrape_patrika),
        ("Nai Dunia", scrape_naidunia),
        ("Navbharat", scrape_navbharat),
        ("Dainik Jagran", scrape_jagran),
        ("Amar Ujala", scrape_amarujala),
        ("Tender Notice India", scrape_tendernotice),
        ("India Tender Notice", scrape_indiatendernotice),
        ("Public Notice India", scrape_publicnotice),
    ]

    for keyword in PRINT_KEYWORDS:
        for label, scraper in newspaper_scrapers:
            # shorter timeout for lightweight newspaper scrapers
            tasks.append(
                asyncio.create_task(_run_sync_and_log(label, scraper, keyword))
            )

    # Optional OCR epaper (run in thread)
    try:
        from app.fetchers.epaper_ocr import scrape_epapers_for_mp

        now = datetime.now(timezone.utc)
        if now.hour == 2:
            tasks.append(
                asyncio.create_task(
                    _run_sync_and_log(
                        "Epaper OCR", lambda: scrape_epapers_for_mp("printing")
                    )
                )
            )
    except Exception:
        pass

    # Await all tasks and collect results
    results = await asyncio.gather(*tasks)
    for _label, raw in results:
        all_raw.extend(raw or [])

    # Deduplicate, normalise and upsert
    normalised = [normalise_tender(r) for r in all_raw]
    tenders = deduplicate_tenders([tender for tender in normalised if tender is not None])
    new_ids = await _upsert_tenders(tenders)
    alert_count = await send_matching_alerts(new_ids)
    print(
        "fetch_cycle_summary "
        f"total_new_tenders={len(new_ids)} alert_emails_dispatched={alert_count}"
    )
    return len(new_ids)


async def send_matching_alerts(new_tender_ids: list[int]) -> int:
    if not new_tender_ids:
        return 0

    now = datetime.now(timezone.utc)
    async with async_session() as session:
        tender_rows = await session.scalars(
            select(Tender)
            .where(Tender.id.in_(new_tender_ids))
            .where(Tender.portal_source.in_(ACTIVE_TENDER_SOURCES))
        )
        tenders = list(tender_rows)
        if not tenders:
            return 0

        subscriber_rows = await session.scalars(
            select(AlertSubscription).where(
                AlertSubscription.is_active.is_(True),
                or_(
                    AlertSubscription.confirmed.is_(True),
                    AlertSubscription.is_confirmed.is_(True),
                ),
            )
        )
        subscribers = list(subscriber_rows)
        sent_count = 0
        for subscriber in subscribers:
            keyword = (
                subscriber.keyword
                or (subscriber.keywords[0] if subscriber.keywords else "")
            ).strip()
            if not keyword:
                continue
            matches = [
                tender for tender in tenders if _tender_matches_keyword(tender, keyword)
            ]
            if not matches:
                continue
            if subscriber.frequency == "daily":
                last_alerted = subscriber.last_alerted_at or subscriber.last_sent
                if last_alerted and last_alerted > now - timedelta(hours=23):
                    continue

            unsubscribe_token = subscriber.token or subscriber.confirm_token or ""
            unsubscribe_url = (
                f"{get_settings().BACKEND_URL.rstrip('/')}/api/alerts/{unsubscribe_token}"
                if unsubscribe_token
                else None
            )
            if send_tender_alert_email(
                subscriber.email,
                keyword,
                matches,
                unsubscribe_url=unsubscribe_url,
            ):
                subscriber.last_alerted_at = now
                subscriber.last_sent = now
                sent_count += 1

        if sent_count:
            await session.commit()
        return sent_count


def _tender_matches_keyword(tender: Tender, keyword: str) -> bool:
    needle = keyword.casefold()
    title = (tender.title or "").casefold()
    keywords = " ".join(tender.keywords or []).casefold()
    return needle in title or needle in keywords


@celery_app.task(name="app.tasks.fetch_job.fetch_all_tenders")
def fetch_all_tenders() -> int:
    return asyncio.run(run_fetch_cycle())
