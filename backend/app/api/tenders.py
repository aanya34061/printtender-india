import inspect
import json
import secrets
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import quote, urljoin, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import Select, asc, desc, func, select, text, or_
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
from bs4 import BeautifulSoup

from app.database import async_session, get_db
from app.fetchers.deeplinks import (
    build_deep_link,
    classify_link,
    extract_nic_tender_id,
    has_nic_direct_sp,
    is_document_download_link,
    is_brittle_nic_direct_link,
    is_generic_link,
)
from app.models import Tender
from app.processing.relevance import build_printing_relevance_predicate, is_printing_relevant_text
from app.processing.value_parser import extract_value_text, parse_value
from app.schemas import TenderRead
from app.sources import (
    ACTIVE_TENDER_SOURCES,
    NEWSPAPER_SOURCES,
    canonicalize_source,
    display_source,
    expand_source_filter,
    is_active_source,
)

router = APIRouter()

SortOption = Literal["deadline_asc", "newest", "value_desc", "value_asc"]
PORTAL_PROXY_TTL_SECONDS = 20 * 60
PORTAL_PROXY_SESSIONS: dict[str, dict[str, Any]] = {}
LIST_CACHE_TTL_SECONDS = 300
LIST_TENDER_CACHE: dict[tuple[Any, ...], tuple[float, dict[str, Any]]] = {}
NATIONAL_BANK_TENDER_SOURCES = {
    "PNB Tenders",
    "Canara Bank Tenders",
    "Central Bank of India Tenders",
    "Bank of India Tenders",
    "Indian Bank Tenders",
    "UCO Bank Tenders",
    "Indian Overseas Bank Tenders",
    "LIC Tenders",
}
PORTAL_BASES = {
    "CPPP": "https://eprocure.gov.in/eprocure/app",
    "MP Tenders": "https://mptenders.gov.in/nicgep/app",
    "eproc.mp.gov.in": "https://eproc.mp.gov.in/nicgep/app",
    "State-MP": "https://mptenders.gov.in/nicgep/app",
    "Maharashtra Tenders": "https://mahatenders.gov.in/nicgep/app",
    "State-MH": "https://mahatenders.gov.in/nicgep/app",
}


def list_fallback_tenders(**kwargs):
    return {
        "tenders": [],
        "total": 0,
        "page": kwargs.get("page", 1),
        "pages": 1,
    }


def get_fallback_tender(tender_id: int):
    return None


def _visible_value_inr(tender: Any) -> float:
    stored = float(getattr(tender, "value_inr", None) or 0)
    if stored > 0:
        return stored
    embedded = extract_value_text(
        getattr(tender, "title", None),
        getattr(tender, "organisation", None),
        getattr(tender, "ref_number", None),
    )
    return parse_value(embedded)


def _serialize_tender(t: Tender) -> dict:
    """Convert ORM Tender to dict, always with a usable link and link_type."""
    # Fast path for serialization without Pydantic validation for every row in a list
    raw_portal_source = t.portal_source or ""
    raw_url = (t.portal_url or "").strip()
    url = raw_url
    tid = getattr(t, "tender_id", None)
    verified = getattr(t, "link_verified", False)
    rebuild_tid = tid
    if is_brittle_nic_direct_link(url) and rebuild_tid == extract_nic_tender_id(url):
        rebuild_tid = None

    # RE-RESOLVE BRITTLE LINKS: If it's a generic link OR a brittle NIC DirectLink, rebuild it.
    # NIC DirectLinks (containing sp=S...) frequently cause 'Session Timeout'.
    if is_generic_link(url) or has_nic_direct_sp(url):
        url = build_deep_link(raw_portal_source, t.ref_number, rebuild_tid)
        verified = False
    elif raw_portal_source == "GeM" and is_document_download_link(url):
        url = build_deep_link("GeM", t.ref_number, None)
        verified = False

    return {
        "id": t.id,
        "ref_number": t.ref_number,
        "title": t.title,
        "organisation": t.organisation,
        "state": t.state,
        "portal_source": display_source(raw_portal_source, raw_url),
        "category": t.category,
        "value_inr": _visible_value_inr(t),
        "emd_amount": float(t.emd_amount) if t.emd_amount else 0,
        "bid_end_date": t.bid_end_date,
        "published_date": t.published_date,
        "portal_url": url,
        "tender_id": tid,
        "link_type": classify_link(url, verified),
        "link_verified": verified,
        "keywords": t.keywords or [],
        "relevance_score": t.relevance_score,
        "fetched_at": t.fetched_at,
        "is_active": t.is_active,
    }


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
    if portal_source in {"GeM", "gem.gov.in"}:
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


def _prune_portal_proxy_sessions() -> None:
    now = time.time()
    expired = [
        token
        for token, payload in PORTAL_PROXY_SESSIONS.items()
        if now - payload.get("created_at", 0) > PORTAL_PROXY_TTL_SECONDS
    ]
    for token in expired:
        PORTAL_PROXY_SESSIONS.pop(token, None)


def _cache_key_for_tender_list(
    *,
    q: str,
    state: str | None,
    portal: str | None,
    category: str | None,
    deadline_within_days: int,
    min_value: float | None,
    max_value: float | None,
    sort: SortOption,
    page: int,
    limit: int,
) -> tuple[Any, ...]:
    return (
        q.strip(),
        state,
        portal,
        category,
        deadline_within_days,
        min_value,
        max_value,
        sort,
        page,
        limit,
    )


def _get_cached_tender_list(cache_key: tuple[Any, ...]) -> dict[str, Any] | None:
    cached = LIST_TENDER_CACHE.get(cache_key)
    if cached is None:
        return None
    expires_at, payload = cached
    if time.time() >= expires_at:
        LIST_TENDER_CACHE.pop(cache_key, None)
        return None
    return deepcopy(payload)


def _set_cached_tender_list(cache_key: tuple[Any, ...], payload: dict[str, Any]) -> None:
    LIST_TENDER_CACHE[cache_key] = (time.time() + LIST_CACHE_TTL_SECONDS, deepcopy(payload))


def _has_open_deadline(tender: Tender) -> bool:
    deadline = tender.bid_end_date
    if deadline is None:
        return False
    if deadline.tzinfo is None:
        deadline = deadline.replace(tzinfo=timezone.utc)
    return deadline > datetime.now(timezone.utc)


def _is_printing_relevant_tender(tender: Tender) -> bool:
    text = " ".join(
        part.strip()
        for part in (
            tender.title or "",
            tender.organisation or "",
            tender.ref_number or "",
        )
        if part and part.strip()
    )
    return is_printing_relevant_text(text, tender.keywords or [])


def _extract_portal_search_payload(html: str) -> dict[str, str]:
    soup = BeautifulSoup(html, "lxml")
    form = soup.find("form", {"id": "tenderSearch"})
    if form is None:
        raise HTTPException(status_code=502, detail="Portal search form not found")
    return {
        str(field.get("name")): str(field.get("value") or "")
        for field in form.find_all("input")
        if field.get("name")
    }


def _build_portal_session(portal_source: str, ref_number: str) -> tuple[str, str]:
    base_url = PORTAL_BASES.get(portal_source)
    if not base_url:
        raise HTTPException(status_code=400, detail="Portal proxy not supported")

    with httpx.Client(timeout=30, follow_redirects=True) as client:
        home = client.get(base_url)
        home.raise_for_status()
        payload = _extract_portal_search_payload(home.text)
        payload["SearchDescription"] = ref_number
        payload["Go"] = payload.get("Go") or "Go"
        result = client.post(base_url, data=payload)
        result.raise_for_status()
        soup = BeautifulSoup(result.text, "lxml")
        matching_link = None
        for anchor in soup.find_all("a", href=True):
            context = " ".join(anchor.parent.get_text(" ", strip=True).split())
            if ref_number.casefold() in context.casefold():
                matching_link = anchor.get("href")
                break
        if not matching_link:
            raise HTTPException(status_code=404, detail="Tender page not found on portal")

        detail_url = urljoin(base_url, str(matching_link))
        detail = client.get(detail_url)
        detail.raise_for_status()

        token = secrets.token_urlsafe(24)
        PORTAL_PROXY_SESSIONS[token] = {
            "created_at": time.time(),
            "base_url": base_url,
            "portal_origin": f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}",
            "cookies": dict(client.cookies.items()),
        }
        return token, detail.text


def _resolve_portal_detail_url(portal_source: str, ref_number: str) -> tuple[str, str]:
    base_url = PORTAL_BASES.get(portal_source)
    if not base_url:
        raise HTTPException(status_code=400, detail="Portal launch not supported")

    with httpx.Client(timeout=30, follow_redirects=True) as client:
        home = client.get(base_url)
        home.raise_for_status()
        payload = _extract_portal_search_payload(home.text)
        payload["SearchDescription"] = ref_number
        payload["Go"] = payload.get("Go") or "Go"
        result = client.post(base_url, data=payload)
        result.raise_for_status()
        soup = BeautifulSoup(result.text, "lxml")
        matching_link = None
        for anchor in soup.find_all("a", href=True):
            context = " ".join(anchor.parent.get_text(" ", strip=True).split())
            if ref_number.casefold() in context.casefold():
                matching_link = anchor.get("href")
                break
        if not matching_link:
            raise HTTPException(status_code=404, detail="Tender page not found on portal")

        detail_url = urljoin(base_url, str(matching_link))
        detail = client.get(detail_url)
        detail.raise_for_status()

        return f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}", detail_url


def _proxy_same_origin_links(html: str, *, token: str, portal_origin: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    if soup.head is not None:
        base = soup.new_tag("base", href=f"{portal_origin}/")
        soup.head.insert(0, base)

    for tag, attr in (("a", "href"), ("form", "action")):
        for node in soup.find_all(tag):
            raw = node.get(attr)
            if not raw:
                continue
            resolved = urljoin(portal_origin, raw)
            if urlparse(resolved).netloc != urlparse(portal_origin).netloc:
                node[attr] = resolved
                continue
            node[attr] = f"/api/tenders/portal-proxy/{token}?url={quote(resolved, safe='')}"

    for tag, attr in (("link", "href"), ("script", "src"), ("img", "src")):
        for node in soup.find_all(tag):
            raw = node.get(attr)
            if not raw:
                continue
            node[attr] = urljoin(portal_origin, raw)

    return str(soup)


def _portal_proxy_response(portal_source: str, ref_number: str) -> HTMLResponse:
    if portal_source not in {"CPPP", "MP Tenders", "eproc.mp.gov.in", "Maharashtra Tenders"}:
        raise HTTPException(status_code=400, detail="Portal proxy not supported")
    token, html = _build_portal_session(portal_source, ref_number)
    portal_origin = PORTAL_PROXY_SESSIONS[token]["portal_origin"]
    proxied = _proxy_same_origin_links(html, token=token, portal_origin=portal_origin)
    return HTMLResponse(content=proxied)


def _portal_launch_html(portal_origin: str, detail_url: str) -> str:
    warmup_url = f"{portal_origin}/nicgep/app"
    warmup_js = json.dumps(warmup_url)
    detail_js = json.dumps(detail_url)
    portal_origin_js = json.dumps(portal_origin)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta http-equiv="cache-control" content="no-store" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Opening tender page</title>
  <style>
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: #111827;
      color: #e5e7eb;
      margin: 0;
      min-height: 100vh;
      display: grid;
      place-items: center;
    }}
    .card {{
      max-width: 560px;
      padding: 24px 28px;
      background: rgba(17,24,39,0.92);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 16px;
      box-shadow: 0 20px 60px rgba(0,0,0,0.35);
    }}
    .small {{
      color: #9ca3af;
      font-size: 14px;
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <div class="card">
    <h1 style="margin:0 0 10px;font-size:20px;">Opening live tender page</h1>
    <p class="small">A portal session is being prepared. The page will redirect to the official tender page once the portal session warms up.</p>
    <p class="small">If the redirect is blocked, allow pop-ups for this site.</p>
  </div>
  <script>
    (function () {{
      const warmupUrl = {warmup_js};
      const detailUrl = {detail_js};
      const portalOrigin = {portal_origin_js};

      try {{
        const warmupWin = window.open(warmupUrl, "_blank", "noopener,noreferrer");
        if (warmupWin) {{
          setTimeout(() => {{
            try {{ warmupWin.location = warmupUrl; }} catch (e) {{}}
          }}, 100);
        }}
      }} catch (e) {{}}

      const iframe = document.createElement("iframe");
      iframe.src = warmupUrl;
      iframe.style.display = "none";
      document.body.appendChild(iframe);

      setTimeout(() => {{
        window.location.replace(detailUrl);
      }}, 1400);
    }})();
  </script>
</body>
</html>"""


def _build_base(
    q: str,
    state: str | None,
    portal: str | None,
    category: str | None,
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

    deadline_predicate = (
        (Tender.bid_end_date > now)
        & (Tender.bid_end_date <= now + text(f"interval '{deadline_within_days} days'"))
    )
    qry = qry.where(deadline_predicate).where(Tender.is_active.is_(True))
    qry = qry.where(Tender.portal_source.in_(ACTIVE_TENDER_SOURCES))
    qry = qry.where(build_printing_relevance_predicate(Tender))
    if state:
        qry = qry.where(
            or_(
                Tender.state == state,
                Tender.portal_source.in_(NATIONAL_BANK_TENDER_SOURCES),
            )
        )
    if portal:
        if portal == "etenders.gov.in":
            qry = qry.where(Tender.portal_source == "CPPP")
            qry = qry.where(Tender.portal_url.ilike("%etenders.gov.in%"))
        elif portal == "CPPP":
            qry = qry.where(Tender.portal_source == "CPPP")
            qry = qry.where(
                or_(
                    Tender.portal_url.is_(None),
                    ~Tender.portal_url.ilike("%etenders.gov.in%"),
                )
            )
        else:
            qry = qry.where(Tender.portal_source.in_(expand_source_filter(portal)))
    if category:
        qry = qry.where(Tender.category.ilike(f"%{category}%"))
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


@router.get("/count")
async def count_tenders(
    q: str = Query(default=""),
    state: str | None = None,
    portal: str | None = None,
    category: str | None = None,
    deadline_within_days: int = Query(default=30, ge=1),
    min_value: float | None = None,
    max_value: float | None = None,
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    qry = _build_base(q, state, portal, category, deadline_within_days, min_value, max_value)
    try:
        count = await session.scalar(select(func.count()).select_from(qry.subquery())) or 0
    except (OSError, SQLAlchemyError, TimeoutError) as exc:
        print(f"count_tenders fallback: {type(exc).__name__}: {exc!r}")
        count = 0
    return {"count": count}


@router.get("/portal-launch", response_class=HTMLResponse)
async def portal_launch(
    portal_source: str,
    ref_number: str,
) -> HTMLResponse:
    try:
        portal_origin, detail_url = _resolve_portal_detail_url(
            canonicalize_source(portal_source),
            ref_number.strip(),
        )
        return HTMLResponse(content=_portal_launch_html(portal_origin, detail_url))
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Unable to open portal tender page")


@router.get("")
async def list_tenders(
    response: Response,
    q: str = Query(default=""),
    state: str | None = None,
    portal: str | None = None,
    category: str | None = None,
    deadline_within_days: int = Query(default=30, ge=1),
    min_value: float | None = None,
    max_value: float | None = None,
    sort: SortOption = "deadline_asc",
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "public, max-age=300, stale-while-revalidate=3600"
    cache_key = _cache_key_for_tender_list(
        q=q,
        state=state,
        portal=portal,
        category=category,
        deadline_within_days=deadline_within_days,
        min_value=min_value,
        max_value=max_value,
        sort=sort,
        page=page,
        limit=limit,
    )
    cached = _get_cached_tender_list(cache_key)
    if cached is not None:
        return cached

    try:
        payload = await _build_tender_list_payload(
            session=session,
            q=q,
            state=state,
            portal=portal,
            category=category,
            deadline_within_days=deadline_within_days,
            min_value=min_value,
            max_value=max_value,
            sort=sort,
            page=page,
            limit=limit,
        )
        _set_cached_tender_list(cache_key, payload)
        return payload
    except (OSError, SQLAlchemyError, TimeoutError) as exc:
        print(f"list_tenders fallback: {type(exc).__name__}: {exc!r}")
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


async def _build_tender_list_payload(
    *,
    session: AsyncSession,
    q: str,
    state: str | None,
    portal: str | None,
    category: str | None,
    deadline_within_days: int,
    min_value: float | None,
    max_value: float | None,
    sort: SortOption,
    page: int,
    limit: int,
) -> dict[str, Any]:
    qry = _build_base(q, state, portal, category, deadline_within_days, min_value, max_value)
    offset = (page - 1) * limit
    sorted_qry = _apply_sort(qry, sort)

    final_qry = sorted_qry.add_columns(func.count().over().label("total_count"))
    result = await session.execute(final_qry.limit(limit).offset(offset))

    rows = result.all()
    if inspect.isawaitable(rows):
        close = getattr(rows, "close", None)
        if callable(close):
            close()
        raise OSError("database result unavailable")
    if not rows:
        return {"tenders": [], "total": 0, "page": page, "pages": 1}

    total = rows[0].total_count
    tenders = [_serialize_tender(row[0]) for row in rows]
    pages = max(1, -(-total // limit))
    return {"tenders": tenders, "total": total, "page": page, "pages": pages}


async def prewarm_tender_list_cache() -> None:
    warm_specs = [
        {
            "q": "",
            "state": None,
            "portal": None,
            "category": None,
            "deadline_within_days": 30,
            "min_value": None,
            "max_value": None,
            "sort": "deadline_asc",
            "page": 1,
            "limit": 6,
        },
        {
            "q": "",
            "state": None,
            "portal": None,
            "category": None,
            "deadline_within_days": 30,
            "min_value": None,
            "max_value": None,
            "sort": "deadline_asc",
            "page": 2,
            "limit": 6,
        },
        {
            "q": "",
            "state": None,
            "portal": None,
            "category": None,
            "deadline_within_days": 30,
            "min_value": None,
            "max_value": None,
            "sort": "deadline_asc",
            "page": 3,
            "limit": 6,
        },
        {
            "q": "",
            "state": None,
            "portal": None,
            "category": None,
            "deadline_within_days": 3,
            "min_value": None,
            "max_value": None,
            "sort": "deadline_asc",
            "page": 1,
            "limit": 5,
        },
    ]
    async with async_session() as session:
        for spec in warm_specs:
            try:
                cache_key = _cache_key_for_tender_list(**spec)
                if _get_cached_tender_list(cache_key) is not None:
                    continue
                payload = await _build_tender_list_payload(session=session, **spec)
                _set_cached_tender_list(cache_key, payload)
            except Exception as exc:
                print(f"tender prewarm skipped spec={spec}: {exc}")


@router.get("/{tender_id}")
async def get_tender(
    tender_id: int, session: AsyncSession = Depends(get_db)
) -> dict[str, Any]:
    try:
        tender = await session.get(Tender, tender_id)
        if (
            tender is None
            or not is_active_source(tender.portal_source)
            or not tender.is_active
            or not _has_open_deadline(tender)
            or not _is_printing_relevant_tender(tender)
        ):
            raise HTTPException(status_code=404, detail="Tender not found")
        # For single item detail, using Pydantic validation is fine and safer
        data = TenderRead.model_validate(tender).model_dump()

        # Apply the same link logic as in list
        raw_portal_source = tender.portal_source or ""
        raw_url = (tender.portal_url or "").strip()
        url = raw_url
        tid = getattr(tender, "tender_id", None)
        verified = getattr(tender, "link_verified", False)
        rebuild_tid = tid
        if is_brittle_nic_direct_link(url) and rebuild_tid == extract_nic_tender_id(url):
            rebuild_tid = None

        # RE-RESOLVE BRITTLE LINKS: If it's a generic link OR a brittle NIC DirectLink, rebuild it.
        if is_generic_link(url) or has_nic_direct_sp(url):
            url = build_deep_link(raw_portal_source, tender.ref_number, rebuild_tid)
            verified = False
        elif raw_portal_source == "GeM" and is_document_download_link(url):
            url = build_deep_link("GeM", tender.ref_number, None)
            verified = False

        data["portal_source"] = display_source(raw_portal_source, raw_url)
        data["value_inr"] = _visible_value_inr(tender)
        data["portal_url"] = url
        data["link_type"] = classify_link(url, verified)
        data["apply_steps"] = _apply_steps(tender.portal_source, tender.state)
        return data
    except HTTPException:
        raise
    except (OSError, SQLAlchemyError, TimeoutError):
        tender = get_fallback_tender(tender_id)
        if tender is None:
            raise HTTPException(status_code=404, detail="Tender not found")
        data = dict(tender)
        data["apply_steps"] = _apply_steps(data.get("portal_source"), data.get("state"))
        return data


@router.get("/{tender_id}/portal-view", response_class=HTMLResponse)
async def open_tender_portal_view(
    tender_id: int, session: AsyncSession = Depends(get_db)
) -> HTMLResponse:
    try:
        tender = await session.get(Tender, tender_id)
        if (
            tender is None
            or not is_active_source(tender.portal_source)
            or not tender.is_active
            or not _has_open_deadline(tender)
            or not _is_printing_relevant_tender(tender)
        ):
            raise HTTPException(status_code=404, detail="Tender not found")
        portal_source = canonicalize_source(tender.portal_source or "")
        ref_number = tender.ref_number or ""
    except HTTPException:
        raise
    except (OSError, SQLAlchemyError, TimeoutError):
        tender = get_fallback_tender(tender_id)
        if tender is None:
            raise HTTPException(status_code=404, detail="Tender not found")
        portal_source = canonicalize_source(str(tender.get("portal_source") or ""))
        ref_number = str(tender.get("ref_number") or "")

    if portal_source not in {"CPPP", "MP Tenders", "eproc.mp.gov.in", "Maharashtra Tenders"}:
        raise HTTPException(status_code=400, detail="Portal proxy not supported")

    try:
        return _portal_proxy_response(portal_source, ref_number)
    except httpx.HTTPError:
        raise HTTPException(status_code=502, detail="Unable to open portal tender page")


@router.get("/portal-proxy/{token}", response_class=HTMLResponse)
async def portal_proxy_follow(token: str, url: str) -> HTMLResponse:
    _prune_portal_proxy_sessions()
    payload = PORTAL_PROXY_SESSIONS.get(token)
    if payload is None:
        raise HTTPException(status_code=410, detail="Portal session expired")

    portal_origin = str(payload["portal_origin"])
    resolved = urljoin(portal_origin, url)
    if urlparse(resolved).netloc != urlparse(portal_origin).netloc:
        raise HTTPException(status_code=400, detail="Invalid proxy target")

    with httpx.Client(
        timeout=30,
        follow_redirects=True,
        cookies=payload.get("cookies", {}),
    ) as client:
        response = client.get(resolved)
        response.raise_for_status()
        payload["cookies"] = dict(client.cookies.items())
        payload["created_at"] = time.time()

    proxied = _proxy_same_origin_links(response.text, token=token, portal_origin=portal_origin)
    return HTMLResponse(content=proxied)
