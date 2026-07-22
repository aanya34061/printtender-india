from datetime import datetime, timedelta, timezone
from copy import deepcopy
import os
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Response
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import case, distinct, func, select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session, get_db
from app.models import AlertSubscription, FetchLog, Tender
from app.processing.relevance import build_printing_relevance_predicate
from app.sources import (
    ACTIVE_FETCH_SOURCES,
    ACTIVE_TENDER_SOURCES,
    NEWSPAPER_SOURCES,
    canonicalize_source,
    display_source,
)

router = APIRouter()
STATS_CACHE_TTL_SECONDS = 30
BUSINESS_TIMEZONE = ZoneInfo("Asia/Kolkata")
_STATS_CACHE: dict[str, object] = {"expires_at": 0.0, "payload": None}


def _configured_portal_labels() -> tuple[str, ...]:
    labels: list[str] = []
    seen: set[str] = set()
    for source in ACTIVE_TENDER_SOURCES:
        label = display_source(source) or canonicalize_source(source) or source
        if label not in seen:
            labels.append(label)
            seen.add(label)
    return tuple(labels)


def _empty_portal_counts() -> dict[str, int]:
    return {label: 0 for label in _configured_portal_labels()}


def fallback_stats():
    by_portal = _empty_portal_counts()
    return {
        "total_active": 0,
        "total_today": 0,
        "expiring_7_days": 0,
        "new_since_yesterday": 0,
        "states_covered": 0,
        "by_portal": by_portal,
        "by_source_category": {"portal": 0, "newspaper": 0},
        "last_fetch": None,
        "portals_count": len(by_portal),
        "keywords_tracked": 0,
    }


@router.get("")
async def get_stats(
    response: Response, session: AsyncSession = Depends(get_db)
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    now_ts = datetime.now(timezone.utc).timestamp()
    cached_payload = _STATS_CACHE.get("payload")
    if (
        not _should_bypass_stats_cache(session)
        and cached_payload is not None
        and now_ts < float(_STATS_CACHE.get("expires_at", 0.0))
    ):
        return deepcopy(cached_payload)

    try:
        payload = await _build_stats_payload(session, now_ts)
        return deepcopy(payload)
    except (OSError, SQLAlchemyError, TimeoutError) as exc:
        print(f"get_stats fallback: {type(exc).__name__}: {exc!r}")
        return fallback_stats()
    except Exception as exc:
        # Log exception to a file for debugging and re-raise
        try:
            with open("/tmp/printtender_stats_error.log", "a") as fh:
                import traceback

                fh.write(str(datetime.now(timezone.utc)) + " - " + repr(exc) + "\n")
                fh.write(traceback.format_exc() + "\n")
        except Exception:
            pass
        raise


async def _build_stats_payload(
    session: AsyncSession, now_ts: float | None = None
) -> dict:
    try:
        now = datetime.now(timezone.utc)
        today_start, tomorrow_start = _business_day_bounds(now)
        yesterday_start = today_start - timedelta(days=1)
        seven_days = now + timedelta(days=7)
        printing_relevance = build_printing_relevance_predicate(Tender)

        open_bid = or_(Tender.bid_end_date > now, Tender.bid_end_date.is_(None))

        # Combine multiple counts into a single query for performance
        stats_query = select(
            func.count()
            .filter(
                Tender.is_active.is_(True),
                Tender.portal_source.in_(ACTIVE_TENDER_SOURCES),
                open_bid,
                printing_relevance,
            )
            .label("total_active"),
            func.count()
            .filter(
                Tender.is_active.is_(True),
                Tender.published_date >= today_start,
                Tender.published_date < tomorrow_start,
                Tender.portal_source.in_(ACTIVE_TENDER_SOURCES),
                open_bid,
                printing_relevance,
            )
            .label("total_today"),
            func.count()
            .filter(
                Tender.is_active.is_(True),
                Tender.portal_source.in_(ACTIVE_TENDER_SOURCES),
                Tender.bid_end_date > now,
                Tender.bid_end_date <= seven_days,
                printing_relevance,
            )
            .label("expiring_7_days"),
            func.count()
            .filter(
                Tender.is_active.is_(True),
                Tender.published_date >= yesterday_start,
                Tender.published_date < today_start,
                Tender.portal_source.in_(ACTIVE_TENDER_SOURCES),
                open_bid,
                printing_relevance,
            )
            .label("new_since_yesterday"),
            func.count(distinct(Tender.state))
            .filter(
                Tender.is_active.is_(True),
                Tender.portal_source.in_(ACTIVE_TENDER_SOURCES),
                open_bid,
                printing_relevance,
                Tender.state.is_not(None),
            )
            .label("states_covered"),
        )

        stats_result = await session.execute(stats_query)
        stats_row = stats_result.one()

        total_active = stats_row.total_active
        total_today = stats_row.total_today
        expiring_7_days = stats_row.expiring_7_days
        new_since_yesterday = stats_row.new_since_yesterday
        states_covered = stats_row.states_covered

        last_fetch = await session.scalar(
            select(func.max(FetchLog.fetched_at)).where(
                FetchLog.portal.in_(ACTIVE_FETCH_SOURCES)
            )
        )

        rows = await session.execute(
            select(Tender.portal_source, Tender.portal_url, func.count().label("cnt"))
            .where(Tender.is_active.is_(True))
            .where(Tender.portal_source.in_(ACTIVE_TENDER_SOURCES))
            .where(open_bid)
            .where(printing_relevance)
            .group_by(Tender.portal_source, Tender.portal_url)
        )
        by_portal = _empty_portal_counts()
        for source, portal_url, cnt in rows:
            label = (
                display_source(source, portal_url)
                or canonicalize_source(source)
                or "Unknown"
            )
            by_portal[label] = by_portal.get(label, 0) + cnt

        by_source_category = {"portal": 0, "newspaper": 0}
        for source, cnt in by_portal.items():
            if source in NEWSPAPER_SOURCES:
                by_source_category["newspaper"] += cnt
            else:
                by_source_category["portal"] += cnt

        alert_rows = await session.scalars(
            select(AlertSubscription.keywords).where(
                AlertSubscription.is_active.is_(True)
            )
        )
        keywords_tracked = len({kw for kws in alert_rows for kw in (kws or [])})

        payload = {
            "total_active": total_active,
            "total_today": total_today,
            "expiring_7_days": expiring_7_days,
            "new_since_yesterday": new_since_yesterday,
            "states_covered": states_covered,
            "by_portal": by_portal,
            "by_source_category": by_source_category,
            "last_fetch": last_fetch,
            "portals_count": len(_configured_portal_labels()),
            "keywords_tracked": keywords_tracked,
        }
        now_ts = now_ts or datetime.now(timezone.utc).timestamp()
        if not _should_bypass_stats_cache(session):
            _STATS_CACHE["payload"] = payload
            _STATS_CACHE["expires_at"] = now_ts + STATS_CACHE_TTL_SECONDS
        return payload
    except Exception:
        raise


async def prewarm_stats_cache() -> None:
    async with async_session() as session:
        try:
            await _build_stats_payload(session)
        except Exception as exc:
            print(f"stats prewarm skipped: {exc}")


def clear_stats_cache() -> None:
    _STATS_CACHE["payload"] = None
    _STATS_CACHE["expires_at"] = 0.0


def _should_bypass_stats_cache(session: AsyncSession) -> bool:
    if "PYTEST_CURRENT_TEST" in os.environ:
        return True
    return type(session).__module__.startswith("unittest.mock")


def _business_day_bounds(now: datetime) -> tuple[datetime, datetime]:
    local_now = now.astimezone(BUSINESS_TIMEZONE)
    local_start = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    local_next = local_start + timedelta(days=1)
    return local_start.astimezone(timezone.utc), local_next.astimezone(timezone.utc)


@router.get("/portals/status")
async def portal_status(session: AsyncSession = Depends(get_db)) -> list[dict]:
    recent_cutoff = datetime.now(timezone.utc) - timedelta(minutes=20)
    subq = (
        select(FetchLog.portal, func.max(FetchLog.fetched_at).label("max_fetched"))
        .where(FetchLog.portal.in_(ACTIVE_FETCH_SOURCES))
        .group_by(FetchLog.portal)
        .subquery()
    )
    latest_rows = await session.execute(
        select(FetchLog).join(
            subq,
            (FetchLog.portal == subq.c.portal)
            & (FetchLog.fetched_at == subq.c.max_fetched),
        )
    )
    logs = latest_rows.scalars().all()

    recent_rows = await session.execute(
        select(
            FetchLog.portal,
            func.max(FetchLog.fetched_at).label("last_fetch"),
            func.sum(FetchLog.tenders_found).label("tenders_found"),
            func.sum(case((FetchLog.status == "ok", 1), else_=0)).label("ok_count"),
        )
        .where(FetchLog.portal.in_(ACTIVE_FETCH_SOURCES))
        .where(FetchLog.fetched_at >= recent_cutoff)
        .group_by(FetchLog.portal)
    )
    recent_by_portal = {row.portal: row for row in recent_rows}
    return [
        {
            "portal": log.portal,
            "last_fetch": (
                recent_by_portal[log.portal].last_fetch
                if log.portal in recent_by_portal
                else log.fetched_at
            ),
            "status": (
                "ok"
                if log.portal in recent_by_portal
                and (recent_by_portal[log.portal].ok_count or 0) > 0
                else log.status
            ),
            "tenders_found": (
                recent_by_portal[log.portal].tenders_found
                if log.portal in recent_by_portal
                else log.tenders_found
            )
            or 0,
        }
        for log in logs
    ]
