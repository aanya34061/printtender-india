import asyncio

from sqlalchemy.dialects.postgresql import insert

from app.database import async_session
from app.fetchers.cppp import CPPPFetcher
from app.fetchers.gem import GeMFetcher
from app.fetchers.state import STATE_PORTALS, StatePortalFetcher
from app.models import Tender
from app.processing.deduplicator import deduplicate_tenders
from app.processing.normaliser import normalise_tender
from app.tasks.celery_app import celery_app


async def run_fetch_cycle() -> int:
    fetchers = [CPPPFetcher(), GeMFetcher(), *[StatePortalFetcher(portal) for portal in STATE_PORTALS]]
    raw_tenders = []
    for fetcher in fetchers:
        raw_tenders.extend(await fetcher.fetch())

    tenders = deduplicate_tenders([normalise_tender(raw) for raw in raw_tenders])
    async with async_session() as session:
        for tender in tenders:
            stmt = insert(Tender).values(**tender.model_dump()).on_conflict_do_update(
                index_elements=["ref_number"],
                set_={
                    "title": tender.title,
                    "organisation": tender.organisation,
                    "state": tender.state,
                    "portal_source": tender.portal_source,
                    "category": tender.category,
                    "value_inr": tender.value_inr,
                    "emd_amount": tender.emd_amount,
                    "bid_end_date": tender.bid_end_date,
                    "published_date": tender.published_date,
                    "portal_url": tender.portal_url,
                    "keywords": tender.keywords,
                    "relevance_score": tender.relevance_score,
                    "is_active": tender.is_active,
                },
            )
            await session.execute(stmt)
        await session.commit()
    return len(tenders)


@celery_app.task(name="app.tasks.fetch_job.fetch_all_sources")
def fetch_all_sources() -> int:
    return asyncio.run(run_fetch_cycle())
