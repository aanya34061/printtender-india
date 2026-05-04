from __future__ import annotations

import asyncio

from sqlalchemy import or_, select

from app.database import async_session
from app.fetchers.deeplinks import (
    GENERIC_HOMEPAGE_URLS,
    build_deep_link,
    classify_link,
    is_generic_link,
)
from app.models import Tender


async def backfill_bad_links() -> int:
    homepage_values = list(GENERIC_HOMEPAGE_URLS) + [
        f"{url}/" for url in GENERIC_HOMEPAGE_URLS if url
    ]
    async with async_session() as session:
        result = await session.scalars(
            select(Tender).where(
                or_(
                    Tender.portal_url.is_(None),
                    Tender.portal_url == "",
                    Tender.portal_url.in_(homepage_values),
                    Tender.link_type.is_(None),
                    Tender.link_type == "",
                )
            )
        )
        tenders = list(result)
        updated = 0
        for tender in tenders:
            url = (tender.portal_url or "").strip()
            if is_generic_link(url):
                url = build_deep_link(
                    tender.portal_source or "",
                    tender.ref_number,
                    tender.tender_id,
                )
                tender.portal_url = url
                tender.link_verified = False
                tender.link_type = classify_link(url, False)
                updated += 1
            elif tender.link_type not in {"direct", "deep", "search"}:
                tender.link_type = classify_link(url, bool(tender.link_verified))
                updated += 1
        if updated:
            await session.commit()
        return updated


if __name__ == "__main__":
    print(asyncio.run(backfill_bad_links()))
