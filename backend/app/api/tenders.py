from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Tender
from app.schemas import TenderListResponse, TenderRead

router = APIRouter()


@router.get("", response_model=TenderListResponse)
async def list_tenders(
    q: str | None = Query(default=None, min_length=2),
    state: str | None = None,
    portal: str | None = None,
    days: int | None = Query(default=None, ge=1),
    category: str | None = None,
    active_only: bool = True,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=100),
    session: AsyncSession = Depends(get_db),
) -> TenderListResponse:
    query: Select[tuple[Tender]] = select(Tender)

    if q:
        pattern = f"%{q}%"
        query = query.where(or_(Tender.title.ilike(pattern), Tender.organisation.ilike(pattern)))
    if state:
        query = query.where(Tender.state == state)
    if portal:
        query = query.where(Tender.portal_source == portal)
    if category:
        query = query.where(Tender.category == category)
    if active_only:
        query = query.where(Tender.is_active.is_(True))
    if days:
        query = query.where(Tender.bid_end_date <= datetime.now(timezone.utc) + timedelta(days=days))

    count_query = select(func.count()).select_from(query.subquery())
    total = await session.scalar(count_query) or 0
    offset = (page - 1) * limit
    rows = await session.scalars(query.order_by(Tender.bid_end_date.asc().nulls_last()).limit(limit).offset(offset))
    items = [TenderRead.model_validate(row) for row in rows]
    return TenderListResponse(total=total, items=items, page=page, limit=limit)


@router.get("/{tender_id}", response_model=TenderRead)
async def get_tender(tender_id: int, session: AsyncSession = Depends(get_db)) -> TenderRead:
    tender = await session.get(Tender, tender_id)
    if tender is None:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Tender not found")
    return TenderRead.model_validate(tender)
