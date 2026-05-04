import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.database import async_session
from app.email_service import send_tender_alert_email
from app.fetchers.aggregators import (
    scrape_bidassist,
    scrape_eprocure_search,
    scrape_tenderdekho,
    scrape_tendertiger,
)
from app.fetchers.cppp import CPPPFetcher, scrape_cppp_mp
from app.fetchers.gem import GeMFetcher
from app.fetchers.mp_portals import (
    MP_PRINT_KEYWORDS,
    scrape_gem_mp_async,
    scrape_mp_forest,
    scrape_mp_info,
    scrape_mp_pwd,
    scrape_mp_tenders,
    scrape_mpbse,
)
from app.fetchers.state import StateFetcher
from app.models import AlertSubscription, FetchLog, Tender
from app.processing.deduplicator import deduplicate_tenders
from app.processing.normaliser import normalise_tender
from app.tasks.celery_app import celery_app


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
    portal: str, found: int, status: str, error: str | None = None
) -> None:
    async with async_session() as session:
        session.add(
            FetchLog(
                portal=portal,
                fetched_at=datetime.now(timezone.utc),
                tenders_found=found,
                new_added=0,
                status=status,
                error_msg=error,
            )
        )
        await session.commit()


def _fetch_by_source(
    label: str, fetcher_fn: "callable"
) -> tuple[str, list, str | None]:
    try:
        raw = fetcher_fn()
        return label, raw, None
    except Exception as exc:
        return label, [], str(exc)


async def run_fetch_cycle() -> int:
    all_raw: list = []

    # CPPP — synchronous XML fetcher
    _, cppp_raw, cppp_err = _fetch_by_source(
        "CPPP", lambda: CPPPFetcher().fetch_all_keywords()
    )
    all_raw.extend(cppp_raw)
    await _log_fetch(
        "CPPP", len(cppp_raw), "ok" if cppp_err is None else "error", cppp_err
    )

    # GeM — Playwright (async); call _fetch_async directly to avoid asyncio.run() conflict
    gem = GeMFetcher()
    for keyword in gem.keywords:
        try:
            raw = await gem._fetch_async(keyword)
            all_raw.extend(raw)
            await _log_fetch("GeM", len(raw), "ok")
        except Exception as exc:
            await _log_fetch("GeM", 0, "error", str(exc))

    # State portals — synchronous HTTP fetcher (all keywords × all states)
    _, state_raw, state_err = _fetch_by_source(
        "State", lambda: StateFetcher().fetch_all()
    )
    all_raw.extend(state_raw)
    await _log_fetch(
        "State", len(state_raw), "ok" if state_err is None else "error", state_err
    )

    mp_sync_scrapers = [
        ("MP Tenders", scrape_mp_tenders),
        ("MP PWD", scrape_mp_pwd),
        ("CPPP MP", scrape_cppp_mp),
        ("MPBSE", scrape_mpbse),
        ("MP Forest", scrape_mp_forest),
        ("MP Info", scrape_mp_info),
    ]
    for keyword in MP_PRINT_KEYWORDS:
        for label, scraper in mp_sync_scrapers:
            portal_label, raw, err = _fetch_by_source(
                label, lambda s=scraper, k=keyword: s(k)
            )
            all_raw.extend(raw)
            await _log_fetch(
                portal_label, len(raw), "ok" if err is None else "error", err
            )
        try:
            gem_mp_raw = await scrape_gem_mp_async(keyword)
            all_raw.extend(gem_mp_raw)
            await _log_fetch("GeM MP", len(gem_mp_raw), "ok")
        except Exception as exc:
            await _log_fetch("GeM MP", 0, "error", str(exc))

    aggregator_scrapers = [
        ("TenderTiger", scrape_tendertiger),
        ("TenderDekho", scrape_tenderdekho),
        ("BidAssist", scrape_bidassist),
        ("CPPP Search", scrape_eprocure_search),
    ]
    aggregator_counts = {label: 0 for label, _ in aggregator_scrapers}
    for keyword in gem.keywords:
        for label, scraper in aggregator_scrapers:
            portal_label, raw, err = _fetch_by_source(
                label, lambda s=scraper, k=keyword: s(k)
            )
            all_raw.extend(raw)
            aggregator_counts[label] += len(raw)
            await _log_fetch(
                portal_label, len(raw), "ok" if err is None else "error", err
            )
    for label, found in aggregator_counts.items():
        print(f"fetch_cycle_source portal={label} found={found}")

    tenders = deduplicate_tenders([normalise_tender(r) for r in all_raw])
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
            select(Tender).where(Tender.id.in_(new_tender_ids))
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
