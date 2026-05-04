from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Select, asc, desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.fetchers.deeplinks import (
    build_deep_link,
    classify_link,
    is_generic_link,
)
from app.models import Tender
from app.schemas import TenderRead

router = APIRouter()

SortOption = Literal["deadline_asc", "newest", "value_desc", "value_asc"]


def _serialize_tender(t: Tender) -> dict:
    """Convert ORM Tender to dict, always with a usable link and link_type."""
    data = TenderRead.model_validate(t).model_dump()

    url = (t.portal_url or "").strip()
    tid = getattr(t, "tender_id", None)
    verified = getattr(t, "link_verified", False)

    if is_generic_link(url):
        url = build_deep_link(t.portal_source or "", t.ref_number, tid)
        verified = False

    data["portal_url"] = url
    data["link_type"] = classify_link(url, verified)
    return data


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
    label = state or "State"
    return [
        f"Register on {label} eProcurement portal",
        "Get DSC if not already done",
        "Download NIT document",
        "Pay EMD online",
        "Upload technical documents",
        "Submit financial bid before deadline",
    ]


def _build_base(
    q: str,
    state: str | None,
    portal: str | None,
    deadline_within_days: int,
    min_value: float | None,
    max_value: float | None,
) -> Select[tuple[Tender]]:
    now = func.now()
    qry: Select[tuple[Tender]] = (
        select(Tender)
        .where(Tender.search_vector.op("@@")(func.plainto_tsquery("english", q)))
        .where(Tender.bid_end_date > now)
        .where(Tender.is_active.is_(True))
        .where(
            Tender.bid_end_date <= now + text(f"interval '{deadline_within_days} days'")
        )
    )
    if state:
        qry = qry.where(Tender.state == state)
    if portal:
        qry = qry.where(Tender.portal_source == portal)
    if min_value is not None:
        qry = qry.where(Tender.value_inr >= min_value)
    if max_value is not None:
        qry = qry.where(Tender.value_inr <= max_value)
    return qry


def _apply_sort(qry: Select[tuple[Tender]], sort: SortOption) -> Select[tuple[Tender]]:
    if sort == "newest":
        return qry.order_by(desc(Tender.fetched_at))
    if sort == "value_desc":
        return qry.order_by(desc(Tender.value_inr).nulls_last())
    if sort == "value_asc":
        return qry.order_by(asc(Tender.value_inr).nulls_last())
    return qry.order_by(asc(Tender.bid_end_date).nulls_last())  # deadline_asc


@router.get("/count")
async def count_tenders(
    q: str = Query(default="printing"),
    state: str | None = None,
    portal: str | None = None,
    deadline_within_days: int = Query(default=30, ge=1),
    min_value: float | None = None,
    max_value: float | None = None,
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    qry = _build_base(q, state, portal, deadline_within_days, min_value, max_value)
    count = await session.scalar(select(func.count()).select_from(qry.subquery())) or 0
    return {"count": count}


@router.get("")
async def list_tenders(
    q: str = Query(default="printing"),
    state: str | None = None,
    portal: str | None = None,
    deadline_within_days: int = Query(default=30, ge=1),
    min_value: float | None = None,
    max_value: float | None = None,
    sort: SortOption = "deadline_asc",
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    qry = _build_base(q, state, portal, deadline_within_days, min_value, max_value)
    total = await session.scalar(select(func.count()).select_from(qry.subquery())) or 0
    offset = (page - 1) * limit
    rows = await session.scalars(_apply_sort(qry, sort).limit(limit).offset(offset))
    tenders = [_serialize_tender(row) for row in rows]
    pages = max(1, -(-total // limit))
    return {"tenders": tenders, "total": total, "page": page, "pages": pages}


@router.get("/{tender_id}")
async def get_tender(
    tender_id: int, session: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    tender = await session.get(Tender, tender_id)
    if tender is None:
        raise HTTPException(status_code=404, detail="Tender not found")
    data = _serialize_tender(tender)
    data["apply_steps"] = _apply_steps(tender.portal_source, tender.state)
    return data
