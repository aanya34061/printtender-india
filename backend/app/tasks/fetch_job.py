import asyncio
from datetime import datetime, timezone

from sqlalchemy.dialects.postgresql import insert

from app.database import async_session
from app.fetchers.cppp import CPPPFetcher
from app.fetchers.gem import GeMFetcher
from app.fetchers.state import StateFetcher
from app.models import FetchLog, Tender
from app.processing.deduplicator import deduplicate_tenders
from app.processing.normaliser import normalise_tender
from app.tasks.celery_app import celery_app


async def _upsert_tenders(tenders: list) -> None:
    async with async_session() as session:
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
            )
            await session.execute(stmt)
        await session.commit()


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
    await _upsert_tenders(tenders)
    return len(tenders)


@celery_app.task(name="app.tasks.fetch_job.fetch_all_tenders")
def fetch_all_tenders() -> int:
    return asyncio.run(run_fetch_cycle())
