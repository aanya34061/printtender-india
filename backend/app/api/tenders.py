import inspect
import json
import secrets
import time
from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import quote, urlencode, urljoin, urlparse

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
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
    infer_official_link_from_aggregator,
    is_brittle_nic_direct_link,
    is_generic_link,
    stable_nic_tender_id,
)
from app.models import Tender
from app.processing.relevance import (
    build_printing_relevance_predicate,
    is_printing_relevant_text,
)
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
LIST_CACHE_TTL_SECONDS = 60
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
    "MP PWD": "https://mptenders.gov.in/nicgep/app",
    "State-MP": "https://mptenders.gov.in/nicgep/app",
    "State-UP": "https://etender.up.nic.in/nicgep/app",
    "Maharashtra Tenders": "https://mahatenders.gov.in/nicgep/app",
    "State-MH": "https://mahatenders.gov.in/nicgep/app",
    "State-RJ": "https://eproc.rajasthan.gov.in/nicgep/app",
}
PORTAL_VIEW_SOURCES = frozenset(PORTAL_BASES)


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


def _resolved_public_tender_url(
    *,
    portal_source: str,
    ref_number: str | None,
    tender_id: str | None,
    raw_url: str,
    link_verified: bool,
    title: str | None,
    organisation: str | None,
    state: str | None,
) -> tuple[str, bool]:
    url = raw_url
    verified = link_verified
    rebuild_tid = tender_id
    if is_brittle_nic_direct_link(url) and rebuild_tid == extract_nic_tender_id(url):
        rebuild_tid = None

    # NIC DirectLinks (containing sp=S...) frequently cause "Session Timeout".
    if is_generic_link(url) or has_nic_direct_sp(url):
        url = build_deep_link(portal_source, ref_number or "", rebuild_tid)
        verified = False

    official_url = infer_official_link_from_aggregator(
        portal_source,
        ref_number,
        tender_id,
        title=title,
        organisation=organisation,
        state=state,
    )
    if official_url:
        return official_url, False

    return url, verified


def _portal_launch_url(
    request: Request | None,
    portal_source: str,
    ref_number: str | None,
    tender_id: str | None,
) -> str | None:
    if request is None:
        return None
    source = canonicalize_source(portal_source)
    if source not in PORTAL_BASES:
        return None
    params = {"portal_source": source}
    if ref_number:
        params["ref_number"] = ref_number
    if tender_id:
        params["tender_id"] = tender_id
    return f"{request.url_for('portal_launch')}?{urlencode(params)}"


def _serialize_tender(t: Tender, request: Request | None = None) -> dict:
    """Convert ORM Tender to dict, always with a usable link and link_type."""
    # Fast path for serialization without Pydantic validation for every row in a list
    raw_portal_source = t.portal_source or ""
    raw_url = (t.portal_url or "").strip()
    tid = getattr(t, "tender_id", None)
    verified = bool(getattr(t, "link_verified", False))
    url, verified = _resolved_public_tender_url(
        portal_source=raw_portal_source,
        ref_number=t.ref_number,
        tender_id=tid,
        raw_url=raw_url,
        link_verified=verified,
        title=t.title,
        organisation=t.organisation,
        state=t.state,
    )

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
        "portal_open_url": _portal_launch_url(
            request, raw_portal_source, t.ref_number, tid
        ),
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
    request_base_url: str | None = None,
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
        request_base_url,
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


def _set_cached_tender_list(
    cache_key: tuple[Any, ...], payload: dict[str, Any]
) -> None:
    LIST_TENDER_CACHE[cache_key] = (
        time.time() + LIST_CACHE_TTL_SECONDS,
        deepcopy(payload),
    )


def clear_tender_list_cache() -> None:
    LIST_TENDER_CACHE.clear()


def _has_open_deadline(tender: Tender) -> bool:
    deadline = tender.bid_end_date
    if deadline is None:
        return True
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


def _portal_search_terms(ref_number: str, tender_id: str | None) -> list[str]:
    stable_id = stable_nic_tender_id(tender_id)
    if stable_id:
        return [stable_id]
    return [ref_number.strip()] if ref_number.strip() else []


def _matching_portal_detail_link(
    html: str, *, base_url: str, expected_terms: list[str]
) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    candidates: list[tuple[str, str]] = []
    for anchor in soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip()
        if not href:
            continue
        lowered_href = href.casefold()
        if not any(
            marker in lowered_href
            for marker in ("directlink", "frontendtendersbynit", "frontendviewtender")
        ):
            continue
        context = " ".join(
            (anchor.find_parent("tr") or anchor.parent or anchor).get_text(
                " ", strip=True
            ).split()
        )
        candidates.append((context, urljoin(base_url, href)))

    for expected in expected_terms:
        needle = expected.casefold()
        for context, href in candidates:
            if needle and needle in context.casefold():
                return href
    if len(candidates) == 1:
        return candidates[0][1]
    return None


def _search_portal_detail(
    client: httpx.Client,
    *,
    base_url: str,
    ref_number: str,
    tender_id: str | None,
) -> str:
    expected_terms = _portal_search_terms(ref_number, tender_id)
    if not expected_terms:
        raise HTTPException(status_code=404, detail="Tender identifier is missing")

    for search_term in expected_terms:
        home = client.get(base_url)
        home.raise_for_status()
        payload = _extract_portal_search_payload(home.text)
        payload["SearchDescription"] = search_term
        payload["Go"] = payload.get("Go") or "Go"
        result = client.post(base_url, data=payload)
        result.raise_for_status()
        matching_link = _matching_portal_detail_link(
            result.text,
            base_url=base_url,
            expected_terms=expected_terms,
        )
        if matching_link:
            return matching_link

    raise HTTPException(status_code=404, detail="Tender page not found on portal")


def _build_portal_session(
    portal_source: str, ref_number: str, tender_id: str | None = None
) -> tuple[str, str]:
    base_url = PORTAL_BASES.get(portal_source)
    if not base_url:
        raise HTTPException(status_code=400, detail="Portal proxy not supported")

    timeout = httpx.Timeout(12, connect=5)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        detail_url = _search_portal_detail(
            client,
            base_url=base_url,
            ref_number=ref_number,
            tender_id=tender_id,
        )
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


def _resolve_portal_detail_url(
    portal_source: str, ref_number: str, tender_id: str | None = None
) -> tuple[str, str]:
    base_url = PORTAL_BASES.get(portal_source)
    if not base_url:
        raise HTTPException(status_code=400, detail="Portal launch not supported")

    timeout = httpx.Timeout(12, connect=5)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        detail_url = _search_portal_detail(
            client,
            base_url=base_url,
            ref_number=ref_number,
            tender_id=tender_id,
        )
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
            node[attr] = (
                f"/api/tenders/portal-proxy/{token}?url={quote(resolved, safe='')}"
            )

    for tag, attr in (("link", "href"), ("script", "src"), ("img", "src")):
        for node in soup.find_all(tag):
            raw = node.get(attr)
            if not raw:
                continue
            node[attr] = urljoin(portal_origin, raw)

    return str(soup)


def _portal_proxy_response(
    portal_source: str, ref_number: str, tender_id: str | None = None
) -> HTMLResponse:
    if portal_source not in PORTAL_VIEW_SOURCES:
        raise HTTPException(status_code=400, detail="Portal proxy not supported")
    token, html = _build_portal_session(portal_source, ref_number, tender_id)
    portal_origin = PORTAL_PROXY_SESSIONS[token]["portal_origin"]
    proxied = _proxy_same_origin_links(html, token=token, portal_origin=portal_origin)
    return HTMLResponse(content=proxied)


def _portal_launch_html(portal_origin: str, detail_url: str, warmup_url: str) -> str:
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
    deadline_within_days: int | None,
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
        keywords_text = func.array_to_string(Tender.keywords, " ")
        qry = qry.where(
            (Tender.search_vector.op("@@")(tsq))
            | (Tender.title.ilike(ilike_pattern))
            | (Tender.organisation.ilike(ilike_pattern))
            | (keywords_text.ilike(ilike_pattern))
        )

    if deadline_within_days is not None:
        deadline_predicate = or_(
            Tender.bid_end_date.is_(None),
            (
                (Tender.bid_end_date > now)
                & (Tender.bid_end_date <= now + text(f"interval '{deadline_within_days} days'"))
            ),
        )
    else:
        deadline_predicate = or_(
            Tender.bid_end_date.is_(None),
            Tender.bid_end_date > now,
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
        if portal in {"CPPP", "etenders.gov.in"}:
            qry = qry.where(Tender.portal_source == "CPPP")
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
    deadline_within_days: int | None = Query(default=None, ge=1),
    min_value: float | None = None,
    max_value: float | None = None,
    session: AsyncSession = Depends(get_db),
) -> dict[str, int]:
    qry = _build_base(
        q, state, portal, category, deadline_within_days, min_value, max_value
    )
    try:
        count = (
            await session.scalar(select(func.count()).select_from(qry.subquery())) or 0
        )
    except (OSError, SQLAlchemyError, TimeoutError) as exc:
        print(f"count_tenders fallback: {type(exc).__name__}: {exc!r}")
        count = 0
    return {"count": count}


@router.get("/portal-launch", response_class=HTMLResponse)
async def portal_launch(
    portal_source: str,
    ref_number: str = "",
    tender_id: str | None = None,
) -> HTMLResponse:
    source = canonicalize_source(portal_source) or portal_source
    base_url = PORTAL_BASES.get(source or "", "https://mptenders.gov.in/nicgep/app")
    portal_origin = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
    try:
        if source in PORTAL_BASES:
            _, detail_url = _resolve_portal_detail_url(
                source,
                ref_number.strip(),
                tender_id,
            )
            return HTMLResponse(
                content=_portal_launch_html(portal_origin, detail_url, base_url)
            )
    except Exception:
        pass

    fallback_url = build_deep_link(source, ref_number, tender_id)
    return HTMLResponse(
        content=_portal_launch_html(portal_origin, fallback_url, base_url)
    )


@router.get("")
async def list_tenders(
    response: Response,
    request: Request,
    q: str = Query(default=""),
    state: str | None = None,
    portal: str | None = None,
    category: str | None = None,
    deadline_within_days: int | None = Query(default=None, ge=1),
    min_value: float | None = None,
    max_value: float | None = None,
    sort: SortOption = "deadline_asc",
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "public, max-age=15, s-maxage=30"
    cache_key = _cache_key_for_tender_list(
        request_base_url=str(request.base_url),
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
            request=request,
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
    request: Request | None = None,
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
    qry = _build_base(
        q, state, portal, category, deadline_within_days, min_value, max_value
    )
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
    tenders = [_serialize_tender(row[0], request) for row in rows]
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
    tender_id: int, request: Request, session: AsyncSession = Depends(get_db)
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
        tid = getattr(tender, "tender_id", None)
        verified = bool(getattr(tender, "link_verified", False))
        url, verified = _resolved_public_tender_url(
            portal_source=raw_portal_source,
            ref_number=tender.ref_number,
            tender_id=tid,
            raw_url=raw_url,
            link_verified=verified,
            title=tender.title,
            organisation=tender.organisation,
            state=tender.state,
        )

        data["portal_source"] = display_source(raw_portal_source, raw_url)
        data["value_inr"] = _visible_value_inr(tender)
        data["portal_url"] = url
        data["portal_open_url"] = _portal_launch_url(
            request, raw_portal_source, tender.ref_number, tid
        )
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
        portal_tender_id = tender.tender_id
    except HTTPException:
        raise
    except (OSError, SQLAlchemyError, TimeoutError):
        tender = get_fallback_tender(tender_id)
        if tender is None:
            raise HTTPException(status_code=404, detail="Tender not found")
        portal_source = canonicalize_source(str(tender.get("portal_source") or ""))
        ref_number = str(tender.get("ref_number") or "")
        portal_tender_id = str(tender.get("tender_id") or "") or None

    if portal_source not in PORTAL_VIEW_SOURCES:
        raise HTTPException(status_code=400, detail="Portal proxy not supported")

    try:
        return _portal_proxy_response(portal_source, ref_number, portal_tender_id)
    except HTTPException as exc:
        if exc.status_code != 404:
            raise
    except httpx.HTTPError:
        pass

    # Exact proxying can be blocked by a government portal or its WAF.  Keep
    # the click useful by warming the official domain and redirecting to its
    # unique tender-id/reference search instead of returning a dead 404/502.
    base_url = PORTAL_BASES[portal_source]
    portal_origin = f"{urlparse(base_url).scheme}://{urlparse(base_url).netloc}"
    fallback_url = build_deep_link(portal_source, ref_number, portal_tender_id)
    return HTMLResponse(
        content=_portal_launch_html(portal_origin, fallback_url, base_url)
    )


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

    proxied = _proxy_same_origin_links(
        response.text, token=token, portal_origin=portal_origin
    )
    return HTMLResponse(content=proxied)
