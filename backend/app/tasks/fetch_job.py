import asyncio
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.database import async_session
from app.email_service import send_all_categories_email, send_tender_alert_email
from app.fetchers.banks import (
    scrape_bank_of_india,
    scrape_canara_bank,
    scrape_central_bank,
    scrape_indian_bank,
    scrape_iob,
    scrape_lic,
    scrape_pnb,
    scrape_uco_bank,
)
from app.keywords import IMAGE_PRODUCT_KEYWORDS, PRINT_KEYWORDS
from app.models import AlertSubscription, FetchLog, Tender
from app.processing.deduplicator import deduplicate_tenders
from app.processing.normaliser import normalise_tender
from app.sources import ACTIVE_TENDER_SOURCES
from app.tasks.celery_app import celery_app


def _scrape_cppp(keyword: str) -> list[dict]:
    from app.fetchers.cppp import CPPPFetcher

    return CPPPFetcher().fetch(keyword)


def _scrape_gem(keyword: str) -> list[dict]:
    from app.fetchers.gem import GeMFetcher

    return GeMFetcher().fetch(keyword)


def _scrape_tenderdekho(keyword: str) -> list[dict]:
    from app.fetchers.aggregators import scrape_tenderdekho

    return scrape_tenderdekho(keyword)


def _scrape_bidassist(keyword: str) -> list[dict]:
    from app.fetchers.aggregators import scrape_bidassist

    return scrape_bidassist(keyword)


def _dedupe_keywords(keywords: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        key = keyword.casefold()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(keyword)
    return deduped


MP_TENDERS_KEYWORDS = _dedupe_keywords(
    [
        *IMAGE_PRODUCT_KEYWORDS,
        "calendar",
        "book",
        "form",
        "brochure",
        "certificate",
        "answer book",
        "poster",
        "banner",
        "label",
        "envelope",
        "pamphlet",
        "annual report",
    ]
)


def _scrape_mp_tenders(keyword: str) -> list[dict]:
    from app.fetchers.mp_portals import scrape_mp_tenders

    return scrape_mp_tenders(keyword)


def _scrape_mp_eproc(keyword: str) -> list[dict]:
    from app.fetchers.mp_portals import scrape_mp_eproc

    return scrape_mp_eproc(keyword)


def _scrape_mp_pwd(keyword: str) -> list[dict]:
    from app.fetchers.mp_portals import scrape_mp_pwd

    return scrape_mp_pwd(keyword)


def _scrape_mpbse(keyword: str) -> list[dict]:
    from app.fetchers.mp_portals import scrape_mpbse

    return scrape_mpbse(keyword)


def _scrape_mp_forest(keyword: str) -> list[dict]:
    from app.fetchers.mp_portals import scrape_mp_forest

    return scrape_mp_forest(keyword)


def _scrape_mp_info(keyword: str) -> list[dict]:
    from app.fetchers.mp_portals import scrape_mp_info

    return scrape_mp_info(keyword)


def _scrape_state(state_code: str):
    def scraper(keyword: str) -> list[dict]:
        from app.fetchers.state import StateFetcher

        return StateFetcher().fetch(keyword, state_code)

    return scraper


BANK_TENDER_KEYWORDS = (
    "printing",
    "stationery",
    "calendars",
    "diary",
    "registers",
    "books",
    "forms",
    "papers",
    "cards",
    "certificates",
    "files",
    "brochures",
    "policy bonds",
    "envelopes",
    "office stationery",
)

PORTAL_SCRAPERS = (
    ("MP Tenders", _scrape_mp_tenders, MP_TENDERS_KEYWORDS),
    ("eproc.mp.gov.in", _scrape_mp_eproc, MP_TENDERS_KEYWORDS),
    ("CPPP", _scrape_cppp, PRINT_KEYWORDS),
    ("GeM", _scrape_gem, PRINT_KEYWORDS),
    ("PNB Tenders", scrape_pnb, BANK_TENDER_KEYWORDS),
    ("Canara Bank Tenders", scrape_canara_bank, BANK_TENDER_KEYWORDS),
    ("Central Bank of India Tenders", scrape_central_bank, BANK_TENDER_KEYWORDS),
    ("Bank of India Tenders", scrape_bank_of_india, BANK_TENDER_KEYWORDS),
    ("Indian Bank Tenders", scrape_indian_bank, BANK_TENDER_KEYWORDS),
    ("UCO Bank Tenders", scrape_uco_bank, BANK_TENDER_KEYWORDS),
    ("Indian Overseas Bank Tenders", scrape_iob, BANK_TENDER_KEYWORDS),
    ("LIC Tenders", scrape_lic, BANK_TENDER_KEYWORDS),
    ("MP PWD", _scrape_mp_pwd, PRINT_KEYWORDS),
    ("MPBSE", _scrape_mpbse, PRINT_KEYWORDS),
    ("MP Forest", _scrape_mp_forest, PRINT_KEYWORDS),
    ("MP Info", _scrape_mp_info, PRINT_KEYWORDS),
    ("State-MP", _scrape_state("MP"), PRINT_KEYWORDS),
    ("State-UP", _scrape_state("UP"), PRINT_KEYWORDS),
    ("State-MH", _scrape_state("MH"), PRINT_KEYWORDS),
    ("State-RJ", _scrape_state("RJ"), PRINT_KEYWORDS),
    ("TenderDekho", _scrape_tenderdekho, PRINT_KEYWORDS),
    ("BidAssist", _scrape_bidassist, PRINT_KEYWORDS),
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


async def _deactivate_missing_source_tenders(
    source: str, active_ref_numbers: set[str]
) -> int:
    async with async_session() as session:
        stmt = (
            update(Tender)
            .where(Tender.portal_source == source)
            .where(Tender.is_active.is_(True))
            .values(is_active=False, fetched_at=datetime.now(timezone.utc))
        )
        if active_ref_numbers:
            stmt = stmt.where(Tender.ref_number.not_in(active_ref_numbers))
        result = await session.execute(stmt)
        await session.commit()
        return int(result.rowcount or 0)


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


async def run_fetch_cycle(
    *,
    source_labels: set[str] | None = None,
    max_keywords_per_source: int | None = None,
    include_newspapers: bool = True,
) -> int:
    """
    Run fetch cycle across all sources. Parallelise IO-bound synchronous scrapers using
    asyncio.to_thread and run async scrapers concurrently where possible. Add timeouts
    and semaphores to prevent slow/hanging scrapers from blocking the whole cycle.
    """

    all_raw: list = []

    # Portal fetches are IO-bound. Keep concurrency high enough for Vercel's
    # request window while still avoiding an unbounded thread fan-out.
    sem_sync = asyncio.Semaphore(24)
    sem_log = asyncio.Semaphore(1)

    async def _safe_log_fetch(
        source: str, found: int, status: str, error: str | None = None
    ) -> None:
        try:
            async with sem_log:
                await _log_fetch(source, found, status, error)
        except Exception as exc:
            print(
                "fetch_log_skipped "
                f"portal={source!r} status={status!r} reason={exc}"
            )

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
            await _safe_log_fetch(label, len(raw), "ok")
            return label, raw, True
        except asyncio.TimeoutError:
            await _safe_log_fetch(label, 0, "error", "timeout")
            return label, [], False
        except Exception as exc:
            await _safe_log_fetch(label, 0, "error", str(exc))
            return label, [], False

    tasks = []
    source_task_counts: dict[str, int] = defaultdict(int)
    source_success_counts: dict[str, int] = defaultdict(int)

    for label, scraper, keywords in PORTAL_SCRAPERS:
        if source_labels is not None and label not in source_labels:
            continue
        selected_keywords = (
            keywords[:max_keywords_per_source]
            if max_keywords_per_source is not None
            else keywords
        )
        for keyword in selected_keywords:
            source_task_counts[label] += 1
            tasks.append(
                asyncio.create_task(_run_sync_and_log(label, scraper, keyword))
            )

    if include_newspapers:
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

        selected_print_keywords = (
            PRINT_KEYWORDS[:max_keywords_per_source]
            if max_keywords_per_source is not None
            else PRINT_KEYWORDS
        )
        for keyword in selected_print_keywords:
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
    for label, raw, ok in results:
        if ok:
            source_success_counts[label] += 1
        all_raw.extend(raw or [])

    # Deduplicate, normalise and upsert
    normalised = [normalise_tender(r) for r in all_raw]
    tenders = deduplicate_tenders([tender for tender in normalised if tender is not None])
    active_refs_by_source: dict[str, set[str]] = defaultdict(set)
    for tender in tenders:
        source = _tender_field(tender, "portal_source")
        ref_number = _tender_field(tender, "ref_number")
        if source and ref_number:
            active_refs_by_source[source].add(ref_number)

    new_ids = await _upsert_tenders(tenders)
    fully_refreshed_sources = {
        source
        for source, task_count in source_task_counts.items()
        if task_count > 0 and source_success_counts.get(source, 0) == task_count
    }
    deactivated_count = 0
    for source in fully_refreshed_sources:
        deactivated_count += await _deactivate_missing_source_tenders(
            source, active_refs_by_source.get(source, set())
        )
    alert_count = await send_matching_alerts(new_ids)
    print(
        "fetch_cycle_summary "
        f"total_new_tenders={len(new_ids)} "
        f"stale_deactivated={deactivated_count} "
        f"alert_emails_dispatched={alert_count}"
    )
    return len(new_ids)


def _tender_field(tender: object, field: str) -> str | None:
    if isinstance(tender, dict):
        value = tender.get(field)
    else:
        value = getattr(tender, field, None)
    text = str(value or "").strip()
    return text or None


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
            )
        )
        subscribers = list(subscriber_rows)
        sent_count = 0
        for subscriber in subscribers:
            keywords = _subscriber_keywords(subscriber)
            if not keywords:
                continue
            matches = [
                tender for tender in tenders if _tender_matches_any_keyword(tender, keywords)
            ]
            if not matches:
                continue
            if not _subscriber_is_due(subscriber, now):
                continue

            unsubscribe_token = subscriber.token or subscriber.confirm_token or ""
            unsubscribe_url = (
                f"{get_settings().BACKEND_URL.rstrip('/')}/api/alerts/{unsubscribe_token}"
                if unsubscribe_token
                else None
            )
            keyword_label = ", ".join(keywords)
            try:
                sent = send_tender_alert_email(
                    subscriber.email,
                    keyword_label,
                    matches,
                    unsubscribe_url=unsubscribe_url,
                )
            except Exception as exc:
                print(
                    "alert_email_failed "
                    f"subscriber_id={subscriber.id!r} email={subscriber.email!r} "
                    f"error={exc!r}"
                )
                sent = False

            if sent:
                subscriber.last_alerted_at = now
                subscriber.last_sent = now
                sent_count += 1

        if sent_count:
            await session.commit()
        return sent_count


async def send_scheduled_subscriber_mails() -> dict[str, object]:
    now = datetime.now(timezone.utc)
    async with async_session() as session:
        subscriber_rows = await session.scalars(
            select(AlertSubscription).where(
                AlertSubscription.is_active.is_(True),
            )
        )
        subscribers = list(subscriber_rows)
        tender_rows = await session.scalars(
            select(Tender)
            .where(Tender.is_active.is_(True))
            .where(Tender.portal_source.in_(ACTIVE_TENDER_SOURCES))
            .order_by(Tender.fetched_at.desc().nulls_last(), Tender.id.desc())
            .limit(3)
        )
        tenders = list(tender_rows)
        sent_count = 0
        failed: list[str] = []

        for subscriber in subscribers:
            last_sent = subscriber.last_sent
            if last_sent is not None:
                if last_sent.tzinfo is None:
                    last_sent = last_sent.replace(tzinfo=timezone.utc)
                if last_sent > now - timedelta(minutes=30):
                    continue

            try:
                sent = send_all_categories_email(subscriber.email, tenders)
            except Exception as exc:
                print(
                    "scheduled_subscriber_email_failed "
                    f"subscriber_id={subscriber.id!r} email={subscriber.email!r} "
                    f"error={exc!r}"
                )
                sent = False

            if sent:
                subscriber.last_sent = now
                sent_count += 1
            else:
                failed.append(subscriber.email)

        if sent_count:
            await session.commit()

        return {
            "total_subscribers": len(subscribers),
            "sent": sent_count,
            "failed": failed,
        }


def _subscriber_keywords(subscriber: AlertSubscription) -> list[str]:
    values = [
        *(subscriber.keywords or []),
        subscriber.keyword or "",
    ]
    keywords: list[str] = []
    seen: set[str] = set()
    for value in values:
        keyword = " ".join(str(value or "").split())
        key = keyword.casefold()
        if keyword and key not in seen:
            keywords.append(keyword)
            seen.add(key)
    return keywords


def _tender_matches_any_keyword(tender: Tender, keywords: list[str]) -> bool:
    return any(_tender_matches_keyword(tender, keyword) for keyword in keywords)


def _subscriber_is_due(subscriber: AlertSubscription, now: datetime) -> bool:
    frequency = (subscriber.frequency or "daily").casefold()
    if frequency == "instant":
        return True

    last_alerted = subscriber.last_alerted_at or subscriber.last_sent
    if last_alerted is None:
        return True

    if last_alerted.tzinfo is None:
        last_alerted = last_alerted.replace(tzinfo=timezone.utc)
    if frequency == "weekly":
        return last_alerted <= now - timedelta(days=6, hours=23)
    return last_alerted <= now - timedelta(hours=23)


def _tender_matches_keyword(tender: Tender, keyword: str) -> bool:
    needle = keyword.casefold()
    title = (tender.title or "").casefold()
    tender_keywords = " ".join(tender.keywords or []).casefold()
    organisation = (tender.organisation or "").casefold()
    category = (tender.category or "").casefold()
    return (
        needle in title
        or needle in tender_keywords
        or needle in organisation
        or needle in category
    )


@celery_app.task(name="app.tasks.fetch_job.fetch_all_tenders")
def fetch_all_tenders() -> int:
    return asyncio.run(run_fetch_cycle())


@celery_app.task(name="app.tasks.fetch_job.send_scheduled_subscriber_mails_task")
def send_scheduled_subscriber_mails_task() -> dict[str, object]:
    return asyncio.run(send_scheduled_subscriber_mails())
