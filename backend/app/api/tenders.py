from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import Tender
from app.schemas import TenderRead

router = APIRouter()


def _apply_steps(portal_source: str | None, state: str | None) -> list[str]:
    if portal_source == "CPPP":
        return [
            "Register on eprocure.gov.in",
            "Get Class 3 DSC",
            "Download tender document",
            "Prepare EMD via NEFT",
            "Submit technical bid online",
            "Submit financial BOQ online",
        ]
    if portal_source == "GeM":
        return [
            "Register on gem.gov.in as Seller",
            "List products under HSN 4820/4901-4911",
            "Click Participate on the bid",
            "Upload required certificates",
            "Submit quote online",
            "Track status in GeM dashboard",
        ]
    state_label = state or "State"
    return [
        f"Register on {state_label} eProcurement portal",
        "Get DSC if not already done",
        "Download NIT document",
        "Pay EMD online",
        "Upload technical documents",
        "Submit financial bid before deadline",
    ]


def _build_query(
    q: str,
    state: str | None,
    portal: str | None,
    days: int,
    category: str | None,
) -> Select[tuple[Tender]]:
    now = func.now()
    query: Select[tuple[Tender]] = (
        select(Tender)
        .where(
            Tender.search_vector.op("@@")(func.plainto_tsquery("english", q))
        )
        .where(Tender.bid_end_date > now)
        .where(Tender.is_active.is_(True))
        .where(Tender.bid_end_date <= now + text(f"interval '{days} days'"))
    )
    if state:
        query = query.where(Tender.state == state)
    if portal:
        query = query.where(Tender.portal_source == portal)
    if category:
        query = query.where(Tender.category == category)
    return query


@router.get("/count")
async def count_tenders(
    q: str = Query(default="printing"),
    state: str | None = None,
    portal: str | None = None,
    days: int = Query(default=30, ge=1),
    category: str | None = None,
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    query = _build_query(q, state, portal, days, category)
    count = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    return {"count": count}


@router.get("")
async def list_tenders(
    q: str = Query(default="printing"),
    state: str | None = None,
    portal: str | None = None,
    days: int = Query(default=30, ge=1),
    category: str | None = None,
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    query = _build_query(q, state, portal, days, category)
    total = await session.scalar(select(func.count()).select_from(query.subquery())) or 0
    offset = (page - 1) * limit
    rows = await session.scalars(
        query.order_by(Tender.bid_end_date.asc().nulls_last()).limit(limit).offset(offset)
    )
    tenders = [TenderRead.model_validate(row) for row in rows]
    pages = max(1, -(-total // limit))  # ceiling division
    return {"tenders": tenders, "total": total, "page": page, "pages": pages}


@router.get("/{tender_id}")
async def get_tender(
    tender_id: int,
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    tender = await session.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")
    data = TenderRead.model_validate(tender).model_dump()
    data["apply_steps"] = _apply_steps(tender.portal_source, tender.state)
    return data
