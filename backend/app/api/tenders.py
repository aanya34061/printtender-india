from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import Select, asc, desc, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.fallback_mp import get_fallback_tender, list_fallback_tenders
from app.fetchers.deeplinks import (
    build_deep_link,
    classify_link,
    is_document_download_link,
    is_generic_link,
)
from app.models import Tender
from app.schemas import TenderRead
from app.sources import (
    ACTIVE_TENDER_SOURCES,
    NEWSPAPER_SOURCES,
    canonicalize_source,
    expand_source_filter,
    is_active_source,
)

router = APIRouter()

SortOption = Literal["deadline_asc", "newest", "value_desc", "value_asc"]


def _serialize_tender(t: Tender) -> dict:
    """Convert ORM Tender to dict, always with a usable link and link_type."""
    data = TenderRead.model_validate(t).model_dump()

    url = (t.portal_url or "").strip()
    raw_portal_source = t.portal_source or ""
    tid = getattr(t, "tender_id", None)
    verified = getattr(t, "link_verified", False)

    if is_generic_link(url):
        url = build_deep_link(raw_portal_source, t.ref_number, tid)
        verified = False
    elif raw_portal_source == "GeM" and is_document_download_link(url):
        url = build_deep_link("GeM", t.ref_number, None)
        verified = False

    data["portal_source"] = canonicalize_source(raw_portal_source)
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
    if portal_source in NEWSPAPER_SOURCES:
        return [
            "Open the published notice",
            "Copy the reference number",
            "Contact the issuing organisation if offline submission is required",
            "Prepare eligibility, technical, and financial documents",
            "Submit the bid before the deadline",
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
    qry: Select[tuple[Tender]] = select(Tender)

    # Build a broader search predicate: full-text search OR title/organisation/keywords ilike
    if q:
        tsq = func.plainto_tsquery("english", q)
        ilike_pattern = f"%{q}%"
        # array_to_string keywords to match freeform q against keywords list
        keywords_text = func.array_to_string(Tender.keywords, ' ')
        qry = qry.where(
            (
                Tender.search_vector.op("@@")(tsq)
            )
            | (Tender.title.ilike(ilike_pattern))
            | (Tender.organisation.ilike(ilike_pattern))
            | (keywords_text.ilike(ilike_pattern))
        )

    qry = qry.where(Tender.bid_end_date > now).where(Tender.is_active.is_(True)).where(
        Tender.bid_end_date <= now + text(f"interval '{deadline_within_days} days'")
    )
    qry = qry.where(Tender.portal_source.in_(ACTIVE_TENDER_SOURCES))
    if state:
        qry = qry.where(Tender.state == state)
    if portal:
        qry = qry.where(Tender.portal_source.in_(expand_source_filter(portal)))
    if min_value is not None:
        qry = qry.where(Tender.value_inr >= min_value)
    if max_value is not None:
        qry = qry.where(Tender.value_inr <= max_value)

    return qry


def _sort_columns(sort: SortOption):
    if sort == "newest":
        return (desc(Tender.fetched_at).nulls_last(), asc(Tender.id))
    if sort == "value_desc":
        return (desc(Tender.value_inr).nulls_last(), asc(Tender.id))
    if sort == "value_asc":
        return (asc(Tender.value_inr).nulls_last(), asc(Tender.id))
    return (asc(Tender.bid_end_date).nulls_last(), asc(Tender.id))


def _apply_sort(qry: Select[tuple[Tender]], sort: SortOption) -> Select[tuple[Tender]]:
    return qry.order_by(*_sort_columns(sort))


def _apply_source_balanced_sort(
    qry: Select[tuple[Tender]], sort: SortOption
) -> Select[tuple[Tender]]:
    sort_columns = _sort_columns(sort)
    source_rank = func.row_number().over(
        partition_by=Tender.portal_source,
        order_by=sort_columns,
    ).label("source_rank")
    ranked = qry.with_only_columns(
        Tender.id.label("tender_id"),
        source_rank,
    ).subquery()
    return (
        select(Tender)
        .join(ranked, Tender.id == ranked.c.tender_id)
        .order_by(asc(ranked.c.source_rank), *sort_columns)
    )


@router.get("/count")
async def count_tenders(
    q: str = Query(default=""),
    state: str | None = None,
    portal: str | None = None,
    deadline_within_days: int = Query(default=30, ge=1),
    min_value: float | None = None,
    max_value: float | None = None,
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    qry = _build_base(q, state, portal, deadline_within_days, min_value, max_value)
    try:
        count = await session.scalar(select(func.count()).select_from(qry.subquery())) or 0
    except (OSError, SQLAlchemyError):
        from app.fallback_mp import count_fallback_tenders

        count = count_fallback_tenders(
            q=q,
            state=state,
            portal=portal,
            deadline_within_days=deadline_within_days,
            min_value=min_value,
            max_value=max_value,
        )
    return {"count": count}


@router.get("")
async def list_tenders(
    q: str = Query(default=""),
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
    try:
        total = await session.scalar(select(func.count()).select_from(qry.subquery())) or 0
        offset = (page - 1) * limit
        sorted_qry = (
            _apply_sort(qry, sort)
            if portal
            else _apply_source_balanced_sort(qry, sort)
        )
        rows = await session.scalars(sorted_qry.limit(limit).offset(offset))
        tenders = [_serialize_tender(row) for row in rows]
        pages = max(1, -(-total // limit))
        return {"tenders": tenders, "total": total, "page": page, "pages": pages}
    except (OSError, SQLAlchemyError):
        return list_fallback_tenders(
            q=q,
            state=state,
            portal=portal,
            deadline_within_days=deadline_within_days,
            min_value=min_value,
            max_value=max_value,
            sort=sort,
            page=page,
            limit=limit,
        )


@router.get("/{tender_id}")
async def get_tender(
    tender_id: int, session: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    try:
        tender = await session.get(Tender, tender_id)
        if tender is None or not is_active_source(tender.portal_source):
            raise HTTPException(status_code=404, detail="Tender not found")
        data = _serialize_tender(tender)
        data["apply_steps"] = _apply_steps(tender.portal_source, tender.state)
        return data
    except HTTPException:
        raise
    except (OSError, SQLAlchemyError):
        tender = get_fallback_tender(tender_id)
        if tender is None:
            raise HTTPException(status_code=404, detail="Tender not found")
        data = dict(tender)
        data["apply_steps"] = _apply_steps(data.get("portal_source"), data.get("state"))
        return data
