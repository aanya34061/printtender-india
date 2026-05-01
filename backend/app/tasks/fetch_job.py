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
                index_elements=["source", "external_id"],
                set_={
                    "title": tender.title,
                    "buyer": tender.buyer,
                    "state": tender.state,
                    "category": tender.category,
                    "estimated_value": tender.estimated_value,
                    "deadline": tender.deadline,
                    "published_at": tender.published_at,
                    "tender_url": tender.tender_url,
                    "keywords": tender.keywords,
                    "raw_payload": tender.raw_payload,
                },
            )
            await session.execute(stmt)
        await session.commit()
    return len(tenders)


@celery_app.task(name="app.tasks.fetch_job.fetch_all_sources")
def fetch_all_sources() -> int:
    return asyncio.run(run_fetch_cycle())
