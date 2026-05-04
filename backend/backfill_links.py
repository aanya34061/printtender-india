from __future__ import annotations

import asyncio

from sqlalchemy import and_, or_, select

from app.database import async_session, run_startup_migrations
from app.fetchers.deeplinks import (
    GENERIC_HOMEPAGE_URLS,
    NIC_PORTAL_BASES,
    build_deep_link,
    classify_link,
    has_nic_direct_sp,
    is_generic_link,
)
from app.models import Tender


async def backfill_bad_links() -> int:
    homepage_values = list(GENERIC_HOMEPAGE_URLS) + [
        f"{url}/" for url in GENERIC_HOMEPAGE_URLS if url
    ]
    nic_portals = list(NIC_PORTAL_BASES)
    tenderdekho_portals = ["TenderDekho", "Tender Dekho"]
    async with async_session() as session:
        result = await session.scalars(
            select(Tender).where(
                or_(
                    Tender.portal_url.is_(None),
                    Tender.portal_url == "",
                    Tender.portal_url.in_(homepage_values),
                    Tender.link_type.is_(None),
                    Tender.link_type == "",
                    and_(
                        Tender.portal_source == "GeM",
                        or_(
                            Tender.portal_url.is_(None),
                            Tender.portal_url.not_ilike("%bid-details%"),
                        ),
                    ),
                    and_(
                        Tender.portal_source.in_(nic_portals),
                        or_(
                            Tender.portal_url.is_(None),
                            Tender.portal_url.not_ilike("%sp=S%"),
                        ),
                    ),
                    and_(
                        Tender.portal_source.in_(tenderdekho_portals),
                        or_(
                            Tender.portal_url.is_(None),
                            Tender.portal_url.not_ilike("%/tender/%"),
                        ),
                    ),
                )
            )
        )
        tenders = list(result)
        updated = 0
        for tender in tenders:
            url = (tender.portal_url or "").strip()
            is_bad_gem_link = (
                tender.portal_source == "GeM" and "bid-details" not in url
            )
            is_bad_nic_link = (
                tender.portal_source in NIC_PORTAL_BASES and not has_nic_direct_sp(url)
            )
            if is_bad_gem_link or is_bad_nic_link or is_generic_link(url):
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


async def main() -> int:
    await run_startup_migrations()
    return await backfill_bad_links()


if __name__ == "__main__":
    print(asyncio.run(main()))
