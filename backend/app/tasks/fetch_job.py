import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import insert

from app.config import get_settings
from app.database import async_session
from app.email_service import send_tender_alert_email
from app.fetchers.cppp import CPPPFetcher
from app.fetchers.gem import GeMFetcher
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

    tenders = deduplicate_tenders([normalise_tender(r) for r in all_raw])
    new_ids = await _upsert_tenders(tenders)
    await send_matching_alerts(new_ids)
    return len(tenders)


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
