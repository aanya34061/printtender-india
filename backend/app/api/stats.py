from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Tender
from app.schemas import StatsRead

router = APIRouter()


@router.get("", response_model=StatsRead)
async def get_stats(session: AsyncSession = Depends(get_session)) -> StatsRead:
    total_tenders = await session.scalar(select(func.count()).select_from(Tender)) or 0
    active_tenders = await session.scalar(
        select(func.count()).select_from(Tender).where(or_(Tender.deadline.is_(None), Tender.deadline >= datetime.now(timezone.utc)))
    ) or 0

    source_rows = await session.execute(select(Tender.source, func.count()).group_by(Tender.source))
    state_rows = await session.execute(select(Tender.state, func.count()).where(Tender.state.is_not(None)).group_by(Tender.state))

    return StatsRead(
        total_tenders=total_tenders,
        active_tenders=active_tenders,
        sources={source: count for source, count in source_rows.all()},
        states={state: count for state, count in state_rows.all()},
    )
