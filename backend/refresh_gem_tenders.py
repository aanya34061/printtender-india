import asyncio

from sqlalchemy import update

from app.database import async_session
from app.fetchers.gem import GeMFetcher
from app.keywords import PRINT_KEYWORDS
from app.models import Tender
from app.processing.deduplicator import deduplicate_tenders
from app.processing.normaliser import normalise_tender
from app.tasks.fetch_job import _upsert_tenders


async def main() -> None:
    fetcher = GeMFetcher(keywords=PRINT_KEYWORDS)
    raw = fetcher.fetch_all_keywords()
    normalised = [normalise_tender(row) for row in raw]
    tenders = deduplicate_tenders(
        [tender for tender in normalised if tender is not None]
    )

    if not tenders:
        print("No GeM tenders fetched; aborting without modifying existing rows.")
        return

    async with async_session() as session:
        await session.execute(
            update(Tender)
            .where(Tender.portal_source == "GeM")
            .values(is_active=False)
        )
        await session.commit()

    new_ids = await _upsert_tenders(tenders)
    print(
        f"Refreshed GeM tenders fetched={len(tenders)} inserted={len(new_ids)} reactivated_or_updated={len(tenders) - len(new_ids)}"
    )


if __name__ == "__main__":
    asyncio.run(main())
