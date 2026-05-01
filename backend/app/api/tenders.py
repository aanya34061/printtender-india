from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import Tender
from app.schemas import TenderRead, TenderSearchResponse

router = APIRouter()


@router.get("", response_model=TenderSearchResponse)
async def list_tenders(
    q: str | None = Query(default=None, min_length=2),
    state: str | None = None,
    source: str | None = None,
    active_only: bool = True,
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> TenderSearchResponse:
    query: Select[tuple[Tender]] = select(Tender)

    if q:
        pattern = f"%{q}%"
        query = query.where(or_(Tender.title.ilike(pattern), Tender.buyer.ilike(pattern)))
    if state:
        query = query.where(Tender.state == state)
    if source:
        query = query.where(Tender.source == source)
    if active_only:
        query = query.where(or_(Tender.deadline.is_(None), Tender.deadline >= datetime.now(timezone.utc)))

    count_query = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_query) or 0
    rows = await session.scalars(query.order_by(Tender.deadline.asc().nulls_last()).limit(limit).offset(offset))
    items = [TenderRead.model_validate(row) for row in rows]
    return TenderSearchResponse(total=total, items=items)


@router.get("/{tender_id}", response_model=TenderRead)
async def get_tender(tender_id: int, session: AsyncSession = Depends(get_session)) -> TenderRead:
    tender = await session.get(Tender, tender_id)
    if tender is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Tender not found")
    return TenderRead.model_validate(tender)
