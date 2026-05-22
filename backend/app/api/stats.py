from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AlertSubscription, FetchLog, Tender
from app.sources import (
    ACTIVE_FETCH_SOURCES,
    ACTIVE_TENDER_SOURCES,
    NEWSPAPER_SOURCES,
    canonicalize_source,
)

router = APIRouter()


def fallback_stats():
    from app.fallback_mp import fallback_stats as impl

    return impl()


@router.get("")
async def get_stats(session: AsyncSession = Depends(get_db)) -> dict:
    try:
        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        yesterday_start = today_start - timedelta(days=1)
        seven_days = now + timedelta(days=7)

        total_active = (
            await session.scalar(
                select(func.count())
                .select_from(Tender)
                .where(Tender.is_active.is_(True))
                .where(Tender.portal_source.in_(ACTIVE_TENDER_SOURCES))
            )
            or 0
        )
        total_today = (
            await session.scalar(
                select(func.count())
                .select_from(Tender)
                .where(Tender.fetched_at >= today_start)
                .where(Tender.portal_source.in_(ACTIVE_TENDER_SOURCES))
            )
            or 0
        )
        expiring_7_days = (
            await session.scalar(
                select(func.count())
                .select_from(Tender)
                .where(Tender.is_active.is_(True))
                .where(Tender.portal_source.in_(ACTIVE_TENDER_SOURCES))
                .where(Tender.bid_end_date > now)
                .where(Tender.bid_end_date <= seven_days)
            )
            or 0
        )
        new_since_yesterday = (
            await session.scalar(
                select(func.count())
                .select_from(Tender)
                .where(Tender.fetched_at >= yesterday_start)
                .where(Tender.fetched_at < today_start)
                .where(Tender.portal_source.in_(ACTIVE_TENDER_SOURCES))
            )
            or 0
        )
        states_covered = (
            await session.scalar(
                select(func.count(distinct(Tender.state)))
                .where(Tender.is_active.is_(True))
                .where(Tender.portal_source.in_(ACTIVE_TENDER_SOURCES))
                .where(Tender.state.is_not(None))
            )
            or 0
        )
        last_fetch = await session.scalar(
            select(func.max(FetchLog.fetched_at)).where(
                FetchLog.portal.in_(ACTIVE_FETCH_SOURCES)
            )
        )

        rows = await session.execute(
            select(Tender.portal_source, func.count().label("cnt"))
            .where(Tender.is_active.is_(True))
            .where(Tender.portal_source.in_(ACTIVE_TENDER_SOURCES))
            .group_by(Tender.portal_source)
        )
        by_portal: dict[str, int] = {}
        for source, cnt in rows:
            label = canonicalize_source(source) or "Unknown"
            by_portal[label] = by_portal.get(label, 0) + cnt

        by_source_category = {"portal": 0, "newspaper": 0}
        for source, cnt in by_portal.items():
            if source in NEWSPAPER_SOURCES:
                by_source_category["newspaper"] += cnt
            else:
                by_source_category["portal"] += cnt

        alert_rows = await session.scalars(
            select(AlertSubscription.keywords).where(AlertSubscription.is_active.is_(True))
        )
        keywords_tracked = len({kw for kws in alert_rows for kw in (kws or [])})

        return {
            "total_active": total_active,
            "total_today": total_today,
            "expiring_7_days": expiring_7_days,
            "new_since_yesterday": new_since_yesterday,
            "states_covered": states_covered,
            "by_portal": by_portal,
            "by_source_category": by_source_category,
            "last_fetch": last_fetch,
            "portals_count": len(by_portal),
            "keywords_tracked": keywords_tracked,
        }
    except (OSError, SQLAlchemyError, TimeoutError):
        return fallback_stats()
    except Exception as exc:
        # Log exception to a file for debugging and re-raise
        try:
            with open('/tmp/printtender_stats_error.log', 'a') as fh:
                import traceback
                fh.write(str(datetime.now(timezone.utc)) + ' - ' + repr(exc) + '\n')
                fh.write(traceback.format_exc() + '\n')
        except Exception:
            pass
        raise


@router.get("/portals/status")
async def portal_status(session: AsyncSession = Depends(get_db)) -> list[dict]:
    subq = (
        select(FetchLog.portal, func.max(FetchLog.fetched_at).label("max_fetched"))
        .where(FetchLog.portal.in_(ACTIVE_FETCH_SOURCES))
        .group_by(FetchLog.portal)
        .subquery()
    )
    rows = await session.execute(
        select(FetchLog).join(
            subq,
            (FetchLog.portal == subq.c.portal)
            & (FetchLog.fetched_at == subq.c.max_fetched),
        )
    )
    logs = rows.scalars().all()
    return [
        {
            "portal": log.portal,
            "last_fetch": log.fetched_at,
            "status": log.status,
            "tenders_found": log.tenders_found,
        }
        for log in logs
    ]
