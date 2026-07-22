"""API endpoint tests — database is fully mocked, no real connection required."""

import os
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/postgres"
)
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("RESEND_API_KEY", "re_test")
os.environ.setdefault("FRONTEND_URL", "http://localhost:5173")

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.dialects import postgresql

from app.api import fetch as fetch_api
from app.api import stats as stats_api
from app.api import tenders as tenders_api
from app.database import get_db
from app.main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tender_row(**kwargs):
    defaults = dict(
        id=1,
        ref_number="REF-001",
        title="Printing of answer booklets and stationery",
        organisation="DoPT",
        state="Delhi",
        portal_source="LIC Tenders",
        category="printing",
        value_inr=Decimal("100000"),
        emd_amount=Decimal("5000"),
        bid_end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
        published_date=datetime(2026, 4, 1, tzinfo=timezone.utc),
        portal_url="https://licindia.in/tenders",
        tender_id=None,
        link_type="deep",
        link_verified=False,
        keywords=["printing"],
        relevance_score=80,
        fetched_at=datetime(2026, 5, 1, tzinfo=timezone.utc),
        is_active=True,
        search_vector="'form':3 'govern':2 'print':1",
    )
    defaults.update(kwargs)
    row = MagicMock()
    for k, v in defaults.items():
        setattr(row, k, v)
    return row


def _make_session(
    *, scalar_returns=None, scalars_returns=None, get_returns=None, execute_returns=None
):
    session = AsyncMock()
    scalar_iter = iter(scalar_returns or [0])

    async def _scalar(*args, **kwargs):
        try:
            return next(scalar_iter)
        except StopIteration:
            return 0

    session.scalar.side_effect = _scalar

    scalars_result = MagicMock()
    scalars_result.__iter__ = MagicMock(return_value=iter(scalars_returns or []))
    session.scalars.return_value = scalars_result

    exec_result = MagicMock()
    exec_result.scalars.return_value.all.return_value = []
    if scalars_returns is not None and execute_returns is None:
        total_count = len(scalars_returns or [])
        wrapped_rows = []
        for row in scalars_returns or []:
            wrapped = MagicMock()
            wrapped.total_count = total_count
            wrapped.__getitem__.side_effect = lambda idx, row=row: (
                row if idx == 0 else total_count
            )
            wrapped_rows.append(wrapped)
        exec_result.all.return_value = wrapped_rows
    if execute_returns is not None:
        exec_result.__iter__ = MagicMock(return_value=iter(execute_returns))
        exec_result.scalar_one_or_none = MagicMock(return_value=execute_returns)
    session.execute.return_value = exec_result

    session.get.return_value = get_returns
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    return session


def _override_db(session):
    async def _dep():
        yield session

    app.dependency_overrides[get_db] = _dep


def _clear():
    app.dependency_overrides.clear()
    tenders_api.LIST_TENDER_CACHE.clear()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"
    assert "env" in r.json()


@pytest.mark.asyncio
async def test_database_failure_returns_503():
    async def _broken_db():
        raise OSError("database host not reachable")
        yield

    app.dependency_overrides[get_db] = _broken_db
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/stats")
        assert r.status_code == 503
        assert "Database is unavailable" in r.json()["detail"]
    finally:
        _clear()


@pytest.mark.asyncio
async def test_list_tenders_falls_back_to_mp_feed_on_db_failure(monkeypatch):
    session = AsyncMock()
    session.scalar.side_effect = OSError("database host not reachable")
    _override_db(session)
    monkeypatch.setattr(
        tenders_api,
        "list_fallback_tenders",
        lambda **_: {
            "tenders": [
                {
                    "id": 1,
                    "ref_number": "MP-1",
                    "title": "Printing work",
                    "organisation": "CMHO District Guna",
                    "state": "Madhya Pradesh",
                    "portal_source": "MP Tenders",
                    "category": "printing",
                    "value_inr": 0,
                    "emd_amount": 0,
                    "bid_end_date": "2026-06-06T18:00:00+00:00",
                    "published_date": "2026-05-13T09:00:00+00:00",
                    "portal_url": "https://mptenders.gov.in/nicgep/app",
                    "tender_id": "2026_DHS_506394_1",
                    "link_type": "direct",
                    "link_verified": True,
                    "keywords": ["printing"],
                    "relevance_score": 80,
                    "fetched_at": "2026-05-22T00:00:00+00:00",
                    "is_active": True,
                }
            ],
            "total": 1,
            "page": 1,
            "pages": 1,
        },
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders?state=Madhya%20Pradesh")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["tenders"][0]["portal_source"] == "MP Tenders"
    finally:
        _clear()


@pytest.mark.asyncio
async def test_stats_fall_back_to_mp_feed_on_db_failure(monkeypatch):
    session = AsyncMock()
    session.execute.side_effect = OSError("database host not reachable")
    _override_db(session)
    monkeypatch.setattr(
        stats_api,
        "fallback_stats",
        lambda: {
            "total_active": 2,
            "total_today": 0,
            "expiring_7_days": 1,
            "new_since_yesterday": 0,
            "states_covered": 1,
            "by_portal": {"MP Tenders": 2},
            "by_source_category": {"portal": 2, "newspaper": 0},
            "last_fetch": "2026-05-22T00:00:00+00:00",
            "portals_count": 1,
            "keywords_tracked": 0,
        },
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/stats")
        assert r.status_code == 200
        assert r.json()["by_portal"] == {"MP Tenders": 2}
    finally:
        _clear()


# ---------------------------------------------------------------------------
# Tenders
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_tenders_200():
    row = _make_tender_row()
    _override_db(_make_session(scalar_returns=[1, 1], scalars_returns=[row]))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders")
        assert r.status_code == 200
        body = r.json()
        assert "tenders" in body and "total" in body and "pages" in body
        assert body["tenders"][0]["portal_source"] == "LIC Tenders"
    finally:
        _clear()


@pytest.mark.asyncio
async def test_list_tenders_canonicalizes_maharashtra_portal_source():
    row = _make_tender_row(
        state="Maharashtra",
        portal_source="State-MH",
        portal_url="https://mahatenders.gov.in/nicgep/app",
    )
    _override_db(_make_session(scalar_returns=[1, 1], scalars_returns=[row]))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders?portal=Maharashtra%20Tenders")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["tenders"][0]["portal_source"] == "Maharashtra Tenders"
    finally:
        _clear()


def test_state_filter_keeps_national_bank_portals_visible_for_all_states():
    qry = tenders_api._build_base(
        q="",
        state="Madhya Pradesh",
        portal=None,
        category=None,
        deadline_within_days=30,
        min_value=None,
        max_value=None,
    )

    compiled = str(
        qry.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "tenders.state = 'Madhya Pradesh'" in compiled
    assert "tenders.portal_source IN" in compiled
    assert "Bank of India Tenders" in compiled
    assert "Central Bank of India Tenders" in compiled


def test_default_tender_query_requires_an_open_deadline_for_all_portals():
    qry = tenders_api._build_base(
        q="",
        state=None,
        portal=None,
        category=None,
        deadline_within_days=30,
        min_value=None,
        max_value=None,
    )

    compiled = str(
        qry.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "tenders.bid_end_date > now()" in compiled
    assert "tenders.bid_end_date IS NULL" in compiled


@pytest.mark.asyncio
async def test_list_tenders_canonicalizes_gem_to_domain_label():
    row = _make_tender_row(
        state="Delhi",
        portal_source="GeM",
        portal_url="https://bidplus.gem.gov.in/all-bids?search_bid=GEM%2F2026%2FB%2F7142926",
    )
    _override_db(_make_session(scalar_returns=[1, 1], scalars_returns=[row]))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders?portal=gem.gov.in")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["tenders"][0]["portal_source"] == "gem.gov.in"
    finally:
        _clear()


@pytest.mark.asyncio
async def test_list_tenders_groups_etenders_domain_under_cppp():
    row = _make_tender_row(
        state="Delhi",
        portal_source="CPPP",
        portal_url="https://etenders.gov.in/eprocure/app",
    )
    _override_db(_make_session(scalar_returns=[1, 1], scalars_returns=[row]))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders?portal=CPPP")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["tenders"][0]["portal_source"] == "CPPP"
    finally:
        _clear()


@pytest.mark.asyncio
async def test_list_tenders_exposes_official_nic_portal_search_url():
    row = _make_tender_row(
        portal_source="MP Tenders",
        ref_number="14",
        portal_url=(
            "https://mptenders.gov.in/nicgep/app?page=FrontEndTendersByKeyword"
            "&service=page&keyword=14&searchBy=0&searchDateType=TD"
        ),
        tender_id="2026_DC_505875_1",
        link_verified=False,
    )
    _override_db(_make_session(scalar_returns=[1, 1], scalars_returns=[row]))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders")
        assert r.status_code == 200
        tender = r.json()["tenders"][0]
        assert tender["portal_url"] == (
            "https://mptenders.gov.in/nicgep/app?page=FrontEndTendersByKeyword"
            "&service=page&keyword=2026_DC_505875_1&searchBy=0&searchDateType=TD"
        )
        assert tender["portal_open_url"] == (
            "http://test/api/tenders/portal-launch?portal_source=MP+Tenders"
            "&ref_number=14&tender_id=2026_DC_505875_1"
        )
        assert tender["link_type"] == "search"
    finally:
        _clear()


@pytest.mark.asyncio
async def test_list_tenders_routes_tenderdekho_gem_rows_to_gem_search():
    row = _make_tender_row(
        portal_source="TenderDekho",
        ref_number="BAREILLY",
        title=(
            "LIC Life Insurance Corporation Printing Forms Tender Bareilly "
            "Uttar Pradesh 2026 GEM Service"
        ),
        organisation="LIC Life Insurance Corporation",
        state="Uttar Pradesh",
        portal_url="https://tenderdekho.com/tender-detail/td-2iULMkDygQ",
        tender_id="td-2iULMkDygQ",
        link_verified=True,
    )
    _override_db(_make_session(scalar_returns=[1, 1], scalars_returns=[row]))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders")
        assert r.status_code == 200
        tender = r.json()["tenders"][0]
        assert tender["portal_url"].startswith(
            "https://bidplus.gem.gov.in/all-bids?search_bid="
        )
        assert tender["portal_open_url"] is None
        assert "tenderdekho.com" not in tender["portal_url"]
        assert tender["link_type"] == "search"
    finally:
        _clear()


@pytest.mark.asyncio
async def test_portal_launch_with_tender_id_resolves_exact_state_up_tender(monkeypatch):
    calls = []

    def fake_resolve(portal_source: str, ref_number: str, tender_id: str | None):
        calls.append((portal_source, ref_number, tender_id))
        return (
            "https://etender.up.nic.in",
            "https://etender.up.nic.in/nicgep/app?component=%24DirectLink_0&page=FrontEndAdvancedSearchResult&service=direct&session=T&sp=SACTUAL",
        )

    monkeypatch.setattr(tenders_api, "_resolve_portal_detail_url", fake_resolve)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.get(
            "/api/tenders/portal-launch",
            params={
                "portal_source": "State-UP",
                "ref_number": "COMPSTAT/2026-27/P-12087",
                "tender_id": "2026_UPSFF_1160290_1",
            },
        )
    assert r.status_code == 200
    body = r.text
    assert "https://etender.up.nic.in/nicgep/app" in body
    assert "sp=SACTUAL" in body
    assert calls == [
        ("State-UP", "COMPSTAT/2026-27/P-12087", "2026_UPSFF_1160290_1")
    ]


@pytest.mark.asyncio
async def test_portal_view_supports_state_up(monkeypatch):
    row = _make_tender_row(
        portal_source="State-UP",
        state="Uttar Pradesh",
        ref_number="COMPSTAT/2026-27/P-12087",
        tender_id="2026_UPSFF_1160290_1",
    )
    _override_db(_make_session(get_returns=row))
    calls = []

    def fake_proxy(portal_source: str, ref_number: str, tender_id: str | None):
        calls.append((portal_source, ref_number, tender_id))
        return tenders_api.HTMLResponse("<html>UP tender</html>")

    monkeypatch.setattr(tenders_api, "_portal_proxy_response", fake_proxy)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders/1/portal-view")
        assert r.status_code == 200
        assert calls == [
            ("State-UP", "COMPSTAT/2026-27/P-12087", "2026_UPSFF_1160290_1")
        ]
    finally:
        _clear()


def test_portal_detail_match_prefers_stable_tender_id_over_short_reference():
    html = """
    <table>
      <tr><td><a href="/nicgep/app?component=%24DirectLink_0&amp;sp=SWRONG">
        [Unrelated tender][14][2026_OTHER_100_1]
      </a></td></tr>
      <tr><td><a href="/nicgep/app?component=%24DirectLink_0&amp;sp=SCORRECT">
        [Regarding the Purchase of Stationery][14][2026_DC_505875_1]
      </a></td></tr>
    </table>
    """

    link = tenders_api._matching_portal_detail_link(
        html,
        base_url="https://mptenders.gov.in/nicgep/app",
        expected_terms=["2026_DC_505875_1", "14"],
    )

    assert link is not None
    assert "sp=SCORRECT" in link


@pytest.mark.asyncio
async def test_portal_view_falls_back_to_official_stable_id_search(monkeypatch):
    row = _make_tender_row(
        portal_source="MP Tenders",
        state="Madhya Pradesh",
        ref_number="14",
        tender_id="2026_DC_505875_1",
    )
    _override_db(_make_session(get_returns=row))

    def unavailable_proxy(*_args, **_kwargs):
        raise tenders_api.HTTPException(
            status_code=404, detail="Tender page not found on portal"
        )

    monkeypatch.setattr(tenders_api, "_portal_proxy_response", unavailable_proxy)
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders/1/portal-view")
        assert r.status_code == 200
        assert "mptenders.gov.in/nicgep/app" in r.text
        assert "keyword=2026_DC_505875_1" in r.text
    finally:
        _clear()


@pytest.mark.asyncio
async def test_list_tenders_extracts_embedded_value_for_existing_rows():
    row = _make_tender_row(
        title="Paper-based Printing Services Posted 8 May ₹3.6 L GEM Service",
        value_inr=Decimal("0"),
    )
    _override_db(_make_session(scalar_returns=[1, 1], scalars_returns=[row]))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders")
        assert r.status_code == 200
        body = r.json()
        assert body["tenders"][0]["value_inr"] == 360000.0
    finally:
        _clear()


@pytest.mark.asyncio
async def test_list_tenders_cppp_filter_includes_all_cppp_urls():
    row = _make_tender_row(
        state="Delhi",
        portal_source="CPPP",
        portal_url="https://eprocure.gov.in/eprocure/app",
    )
    _override_db(_make_session(scalar_returns=[1, 1], scalars_returns=[row]))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders?portal=CPPP")
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 1
        assert body["tenders"][0]["portal_source"] == "CPPP"
    finally:
        _clear()


@pytest.mark.asyncio
async def test_list_tenders_empty():
    _override_db(_make_session(scalar_returns=[0, 0], scalars_returns=[]))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders?q=printing")
        assert r.status_code == 200
        assert r.json()["total"] == 0
        assert r.json()["tenders"] == []
    finally:
        _clear()


@pytest.mark.asyncio
async def test_list_tenders_with_filters():
    _override_db(
        _make_session(scalar_returns=[5, 5], scalars_returns=[_make_tender_row()])
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get(
                "/api/tenders?q=printing&state=Delhi&portal=TOI%20Tenders&deadline_within_days=7"
            )
        assert r.status_code == 200
    finally:
        _clear()


@pytest.mark.asyncio
async def test_get_tender_detail():
    row = _make_tender_row()
    _override_db(_make_session(get_returns=row))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders/1")
        assert r.status_code == 200
        body = r.json()
        assert "apply_steps" in body
        assert isinstance(body["apply_steps"], list)
        assert len(body["apply_steps"]) > 0
    finally:
        _clear()


@pytest.mark.asyncio
async def test_get_tender_exposes_mp_tenders_source_and_url():
    row = _make_tender_row(
        portal_source="MP Tenders",
        portal_url=(
            "https://mptenders.gov.in/nicgep/app?component=%24DirectLink"
            "&page=FrontEndTendersByNIT&service=direct&session=T&sp=S123"
        ),
        tender_id="S123",
    )
    _override_db(_make_session(get_returns=row))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders/1")
        assert r.status_code == 200
        body = r.json()
        assert body["portal_source"] == "MP Tenders"
        assert body["portal_url"] == (
            "https://mptenders.gov.in/nicgep/app?page=FrontEndTendersByKeyword"
            "&service=page&keyword=REF-001&searchBy=0&searchDateType=TD"
        )
        assert body["portal_open_url"] == (
            "http://test/api/tenders/portal-launch?portal_source=MP+Tenders"
            "&ref_number=REF-001&tender_id=S123"
        )
    finally:
        _clear()


async def test_get_tender_canonicalizes_gem_to_domain_label():
    row = _make_tender_row(
        portal_source="GeM",
        ref_number="GEM/2026/B/7142926",
        portal_url="https://bidplus.gem.gov.in/all-bids?search_bid=GEM%2F2026%2FB%2F7142926",
        link_type="deep",
        link_verified=False,
    )
    _override_db(_make_session(get_returns=row))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders/1")
        assert r.status_code == 200
        body = r.json()
        assert body["portal_source"] == "gem.gov.in"
        assert body["apply_steps"][0] == "Register on gem.gov.in as Seller"
    finally:
        _clear()


@pytest.mark.asyncio
async def test_get_tender_rebuilds_brittle_mp_session_link_to_official_search():
    row = _make_tender_row(
        portal_source="MP Tenders",
        state="Madhya Pradesh",
        ref_number="MP-CAL-001",
        portal_url=(
            "https://mptenders.gov.in/nicgep/app?component=%24DirectLink_0"
            "&page=FrontEndAdvancedSearchResult&service=direct&session=T&sp=SWp8FvorQMqWExhnmC"
        ),
        tender_id="2026_DOP_1",
    )
    _override_db(_make_session(get_returns=row))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders/1")
        assert r.status_code == 200
        body = r.json()
        assert body["portal_source"] == "MP Tenders"
        assert body["portal_url"] == (
            "https://mptenders.gov.in/nicgep/app?page=FrontEndTendersByKeyword"
            "&service=page&keyword=2026_DOP_1&searchBy=0&searchDateType=TD"
        )
        assert body["link_type"] == "search"
    finally:
        _clear()


@pytest.mark.asyncio
async def test_get_tender_extracts_embedded_value_for_existing_rows():
    row = _make_tender_row(
        title="Paper-based Printing Services Posted 8 May ₹3.6 L GEM Service",
        value_inr=Decimal("0"),
    )
    _override_db(_make_session(get_returns=row))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders/1")
        assert r.status_code == 200
        assert r.json()["value_inr"] == 360000.0
    finally:
        _clear()


@pytest.mark.asyncio
async def test_get_tender_rebuilds_brittle_maharashtra_session_link_to_official_search():
    row = _make_tender_row(
        portal_source="State-MH",
        state="Maharashtra",
        ref_number="MH-CAL-001",
        portal_url=(
            "https://mahatenders.gov.in/nicgep/app?component=%24DirectLink_0"
            "&page=FrontEndAdvancedSearchResult&service=direct&session=T&sp=SWp8FvorQMqWExhnmC"
        ),
        tender_id="SWp8FvorQMqWExhnmC",
    )
    _override_db(_make_session(get_returns=row))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders/1")
        assert r.status_code == 200
        body = r.json()
        assert body["portal_source"] == "Maharashtra Tenders"
        assert body["portal_url"] == (
            "https://mahatenders.gov.in/nicgep/app?page=FrontEndTendersByKeyword"
            "&service=page&keyword=MH-CAL-001&searchBy=0&searchDateType=TD"
        )
        assert body["link_type"] == "search"
    finally:
        _clear()


@pytest.mark.asyncio
async def test_get_tender_rebuilds_maharashtra_direct_nit_to_official_search():
    row = _make_tender_row(
        portal_source="State-MH",
        state="Maharashtra",
        ref_number="MH-CAL-001",
        portal_url=(
            "https://mahatenders.gov.in/nicgep/app?component=%24DirectLink"
            "&page=FrontEndTendersByNIT&service=direct&session=T&sp=S2026_MSBSH_1300024_2"
        ),
        tender_id="S2026_MSBSH_1300024_2",
    )
    _override_db(_make_session(get_returns=row))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders/1")
        assert r.status_code == 200
        body = r.json()
        assert body["portal_source"] == "Maharashtra Tenders"
        assert body["portal_url"] == (
            "https://mahatenders.gov.in/nicgep/app?page=FrontEndTendersByKeyword"
            "&service=page&keyword=2026_MSBSH_1300024_2&searchBy=0&searchDateType=TD"
        )
        assert body["link_type"] == "search"
    finally:
        _clear()


@pytest.mark.asyncio
async def test_portal_launch_returns_redirect_page(monkeypatch):
    monkeypatch.setattr(
        tenders_api,
        "_resolve_portal_detail_url",
        lambda portal_source, ref_number, tender_id=None: (
            "https://mptenders.gov.in",
            "https://mptenders.gov.in/nicgep/app?component=%24DirectLink&page=FrontEndTendersByNIT&service=direct&session=T&sp=S2026_UAD_505750_1",
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.get(
            "/api/tenders/portal-launch",
            params={
                "portal_source": "MP Tenders",
                "ref_number": "32/Stationery dep./2026-27 Katni Date05/05/2026",
            },
        )
    assert r.status_code == 200
    body = r.text
    assert "window.location.replace" in body
    assert "mptenders.gov.in/nicgep/app" in body


@pytest.mark.asyncio
async def test_portal_launch_supports_cppp(monkeypatch):
    monkeypatch.setattr(
        tenders_api,
        "_resolve_portal_detail_url",
        lambda portal_source, ref_number, tender_id=None: (
            "https://eprocure.gov.in",
            "https://eprocure.gov.in/eprocure/app?component=%24DirectLink&page=FrontEndTendersByNIT&service=direct&session=T&sp=S12345678",
        ),
    )
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.get(
            "/api/tenders/portal-launch",
            params={
                "portal_source": "CPPP",
                "ref_number": "04021%2F2026-2027%2FE33479",
            },
        )
    assert r.status_code == 200
    body = r.text
    assert "window.location.replace" in body
    assert "eprocure.gov.in/eprocure/app" in body


@pytest.mark.asyncio
async def test_get_tender_preserves_exact_gem_document_url():
    row = _make_tender_row(
        portal_source="GeM",
        ref_number="GEM/2026/B/7142926",
        portal_url="https://bidplus.gem.gov.in/showbidDocument/8876535",
        link_type="direct",
        link_verified=True,
    )
    _override_db(_make_session(get_returns=row))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders/1")
        assert r.status_code == 200
        body = r.json()
        assert body["portal_url"] == (
            "https://bidplus.gem.gov.in/showbidDocument/8876535"
        )
        assert body["link_type"] == "direct"
    finally:
        _clear()


@pytest.mark.asyncio
async def test_get_tender_rejects_inactive_portal_source():
    row = _make_tender_row(
        portal_source="Retired Portal",
        ref_number="OLD/2025/04/123",
        portal_url="https://example.com/tender",
        tender_id="S12345678",
        link_verified=False,
    )
    _override_db(_make_session(get_returns=row))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders/1")
        assert r.status_code == 404
    finally:
        _clear()


@pytest.mark.asyncio
async def test_get_tender_falls_back_to_mp_feed_on_db_failure(monkeypatch):
    session = AsyncMock()
    session.get.side_effect = OSError("database host not reachable")
    _override_db(session)
    monkeypatch.setattr(
        tenders_api,
        "get_fallback_tender",
        lambda tender_id: {
            "id": tender_id,
            "ref_number": "MP-1",
            "title": "Printing work",
            "organisation": "CMHO District Guna",
            "state": "Madhya Pradesh",
            "portal_source": "MP Tenders",
            "category": "printing",
            "value_inr": 0,
            "emd_amount": 0,
            "bid_end_date": "2026-06-06T18:00:00+00:00",
            "published_date": "2026-05-13T09:00:00+00:00",
            "portal_url": "https://mptenders.gov.in/nicgep/app",
            "tender_id": "2026_DHS_506394_1",
            "link_type": "direct",
            "link_verified": True,
            "keywords": ["printing"],
            "relevance_score": 80,
            "fetched_at": "2026-05-22T00:00:00+00:00",
            "is_active": True,
        },
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders/1")
        assert r.status_code == 200
        body = r.json()
        assert body["portal_source"] == "MP Tenders"
        assert body["apply_steps"]
    finally:
        _clear()


@pytest.mark.asyncio
async def test_get_tender_apply_steps_are_generic():
    row = _make_tender_row()
    _override_db(_make_session(get_returns=row))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders/1")
        steps = r.json()["apply_steps"]
        assert any("Register" in s for s in steps)
    finally:
        _clear()


@pytest.mark.asyncio
async def test_get_tender_not_found():
    _override_db(_make_session(get_returns=None))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders/999")
        assert r.status_code == 404
    finally:
        _clear()


@pytest.mark.asyncio
async def test_tender_count():
    _override_db(_make_session(scalar_returns=[42]))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders/count")
        assert r.status_code == 200
        assert r.json()["count"] == 42
    finally:
        _clear()


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_stats_200():
    _override_db(
        _make_session(
            scalar_returns=[10, 5, 8, 3, 7, datetime(2026, 5, 1, tzinfo=timezone.utc)],
            scalars_returns=[["printing"]],
            execute_returns=[
                ("MP Tenders", "https://mptenders.gov.in/nicgep/app", 4),
                ("LIC Tenders", "https://licindia.in/tenders", 2),
            ],
        )
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/stats")
        assert r.status_code == 200
        body = r.json()
        for key in (
            "total_active",
            "total_today",
            "expiring_7_days",
            "new_since_yesterday",
            "states_covered",
            "by_portal",
            "by_source_category",
            "portals_count",
        ):
            assert key in body, f"missing key: {key}"
        assert body["by_portal"]["MP Tenders"] == 4
        assert body["by_portal"]["LIC Tenders"] == 2
        assert body["by_portal"]["PNB Tenders"] == 0
        assert body["portals_count"] == len(stats_api._configured_portal_labels())
    finally:
        _clear()


@pytest.mark.asyncio
async def test_get_stats_counts_today_from_published_date():
    row = MagicMock()
    row.total_active = 3
    row.total_today = 2
    row.expiring_7_days = 1
    row.new_since_yesterday = 1
    row.states_covered = 2

    stats_result = MagicMock()
    stats_result.one.return_value = row
    portal_result = MagicMock()
    portal_result.__iter__ = MagicMock(return_value=iter([]))

    session = AsyncMock()
    session.execute.side_effect = [stats_result, portal_result]
    session.scalar.return_value = datetime(2026, 6, 3, tzinfo=timezone.utc)
    session.scalars.return_value = []

    await stats_api._build_stats_payload(session)

    stats_query = session.execute.call_args_list[0].args[0]
    compiled = str(stats_query.compile(dialect=postgresql.dialect()))
    assert "published_date" in compiled
    assert "fetched_at" not in compiled


@pytest.mark.asyncio
async def test_get_stats_merges_state_mh_into_maharashtra_tenders():
    _override_db(
        _make_session(
            scalar_returns=[3, 0, 0, 0, 1, datetime(2026, 5, 1, tzinfo=timezone.utc)],
            scalars_returns=[["printing"]],
            execute_returns=[
                ("State-MH", "https://mahatenders.gov.in/nicgep/app", 2),
                ("Maharashtra Tenders", "https://mahatenders.gov.in/nicgep/app", 1),
            ],
        )
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/stats")
        assert r.status_code == 200
        body = r.json()
        assert body["by_portal"]["Maharashtra Tenders"] == 3
        assert "State-MH" not in body["by_portal"]
    finally:
        _clear()


async def test_get_stats_canonicalizes_gem_to_domain_label():
    _override_db(
        _make_session(
            scalar_returns=[2, 0, 0, 0, 1, datetime(2026, 5, 1, tzinfo=timezone.utc)],
            scalars_returns=[["printing"]],
            execute_returns=[("GeM", "https://bidplus.gem.gov.in/all-bids", 2)],
        )
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/stats")
        assert r.status_code == 200
        body = r.json()
        assert body["by_portal"]["gem.gov.in"] == 2
        assert "GeM" not in body["by_portal"]
    finally:
        _clear()


@pytest.mark.asyncio
async def test_get_stats_splits_cppp_and_etenders_by_url_host():
    _override_db(
        _make_session(
            scalar_returns=[3, 0, 0, 0, 1, datetime(2026, 5, 1, tzinfo=timezone.utc)],
            scalars_returns=[["printing"]],
            execute_returns=[
                ("CPPP", "https://eprocure.gov.in/eprocure/app", 2),
                ("CPPP", "https://etenders.gov.in/eprocure/app", 1),
            ],
        )
    )
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/stats")
        assert r.status_code == 200
        body = r.json()
        assert body["by_portal"]["CPPP"] == 3
        assert "etenders.gov.in" not in body["by_portal"]
    finally:
        _clear()


@pytest.mark.asyncio
async def test_portal_status():
    _override_db(_make_session())
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/stats/portals/status")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
    finally:
        _clear()


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_subscribe_valid_201():
    sub_row = MagicMock()
    sub_row.id = 1
    sub_row.email = "press@example.com"
    sub_row.whatsapp = None
    sub_row.keywords = ["printing"]
    sub_row.states = []
    sub_row.frequency = "daily"
    sub_row.is_active = True
    sub_row.is_confirmed = False
    sub_row.confirm_token = "tok"
    sub_row.last_sent = None
    sub_row.created_at = datetime(2026, 5, 1, tzinfo=timezone.utc)

    session = _make_session()

    async def _refresh(obj):
        for attr, val in vars(sub_row).items():
            if not attr.startswith("_"):
                try:
                    setattr(obj, attr, val)
                except Exception:
                    pass

    session.refresh.side_effect = _refresh
    _override_db(session)
    with patch("app.api.alerts.send_confirmation_email", return_value=True), patch(
        "app.api.alerts.send_test_tender_email", return_value=True
    ):
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as c:
                r = await c.post(
                    "/api/alerts/subscribe",
                    json={
                        "email": "press@example.com",
                        "keywords": ["printing"],
                        "frequency": "daily",
                    },
                )
            assert r.status_code == 201
        finally:
            _clear()


@pytest.mark.asyncio
async def test_subscribe_invalid_email_422():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.post(
            "/api/alerts/subscribe",
            json={
                "email": "not-an-email",
                "keywords": ["printing"],
                "frequency": "daily",
            },
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_subscribe_empty_keywords_422():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.post(
            "/api/alerts/subscribe",
            json={"email": "press@example.com", "keywords": [], "frequency": "daily"},
        )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_subscribe_invalid_frequency_422():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.post(
            "/api/alerts/subscribe",
            json={
                "email": "press@example.com",
                "keywords": ["printing"],
                "frequency": "hourly",
            },
        )
    assert r.status_code == 422


# ── New POST /api/alerts endpoint ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_new_alert_endpoint_201():
    session = _make_session()

    async def _refresh(obj):
        obj.id = 99
        obj.email = "test@test.com"
        obj.keywords = ["printing"]
        obj.states = []
        obj.frequency = "daily"
        obj.is_active = True
        obj.is_confirmed = False
        obj.confirm_token = "abc"
        obj.created_at = datetime(2026, 5, 1, tzinfo=timezone.utc)
        obj.last_sent = None

    session.refresh.side_effect = _refresh
    _override_db(session)
    with patch("app.api.alerts.send_confirmation_email"):
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as c:
                r = await c.post(
                    "/api/alerts",
                    json={
                        "email": "test@test.com",
                        "keyword": "printing",
                        "frequency": "daily",
                    },
                )
            assert r.status_code == 201
            assert "message" in r.json()
        finally:
            _clear()


@pytest.mark.asyncio
async def test_new_alert_invalid_email_422():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        r = await c.post("/api/alerts", json={"email": "bad", "keyword": "printing"})
    assert r.status_code == 422


# ── Fetch trigger ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_trigger():
    fetch_api._running_task = None
    fetch_api._running_scope = None
    fetch_api._last_count.clear()
    mocked = AsyncMock(return_value=5)
    with patch("app.api.fetch.run_fetch_cycle", new=mocked):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.post("/api/fetch/trigger")
        assert r.status_code == 200
        assert r.json() == {"status": "triggered", "scope": "live", "count": None}
        await fetch_api._running_task
        assert fetch_api._last_count["count"] == 5
        mocked.assert_awaited_once()
        kwargs = mocked.await_args.kwargs
        assert kwargs["source_labels"] == fetch_api.LIVE_CRON_PORTAL_SOURCES
        assert kwargs["max_keywords_per_source"] == fetch_api.FAST_FETCH_KEYWORD_LIMIT
        assert kwargs["include_newspapers"] is False


@pytest.mark.asyncio
async def test_fetch_trigger_banks_scope_runs_bank_sources_only():
    fetch_api._running_task = None
    fetch_api._running_scope = None
    fetch_api._last_count.clear()
    mocked = AsyncMock(return_value=6)
    with patch("app.api.fetch.run_fetch_cycle", new=mocked):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.post("/api/fetch/trigger?scope=banks")
        assert r.status_code == 200
        assert r.json() == {"status": "triggered", "scope": "banks", "count": None}
        await fetch_api._running_task
        assert fetch_api._last_count["count"] == 6
        mocked.assert_awaited_once()
        kwargs = mocked.await_args.kwargs
        assert kwargs["source_labels"] == {
            "PNB Tenders",
            "Canara Bank Tenders",
            "Central Bank of India Tenders",
            "Bank of India Tenders",
            "Indian Bank Tenders",
            "UCO Bank Tenders",
            "Indian Overseas Bank Tenders",
            "LIC Tenders",
        }
        assert kwargs["include_newspapers"] is False


@pytest.mark.asyncio
async def test_fetch_trigger_lic_scope_runs_lic_source_synchronously():
    fetch_api._running_task = None
    fetch_api._running_scope = None
    fetch_api._last_count.clear()
    mocked = AsyncMock(return_value=4)
    with patch("app.api.fetch.run_fetch_cycle", new=mocked):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.post("/api/fetch/trigger?scope=lic")
        assert r.status_code == 200
        assert r.json() == {"status": "completed", "scope": "lic", "count": 4}
        mocked.assert_awaited_once()
        kwargs = mocked.await_args.kwargs
        assert kwargs["source_labels"] == {"LIC Tenders"}
        assert kwargs["include_newspapers"] is False


@pytest.mark.asyncio
async def test_fetch_cron_default_runs_live_portal_sources():
    mocked = AsyncMock(return_value=8)
    with patch("app.api.fetch.run_fetch_cycle", new=mocked):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/fetch/cron")
        assert r.status_code == 200
        assert r.json() == {"status": "completed", "scope": "live", "count": 8}
        mocked.assert_awaited_once()
        kwargs = mocked.await_args.kwargs
        assert kwargs["source_labels"] == fetch_api.LIVE_CRON_PORTAL_SOURCES
        assert kwargs["max_keywords_per_source"] == fetch_api.FAST_FETCH_KEYWORD_LIMIT
        assert kwargs["include_newspapers"] is False


@pytest.mark.asyncio
async def test_mail_cron_sends_scheduled_subscriber_mails():
    mocked = AsyncMock(
        return_value={
            "total_subscribers": 2,
            "sent": 2,
            "failed": [],
        }
    )
    with patch("app.tasks.fetch_job.send_scheduled_subscriber_mails", new=mocked):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/fetch/mail-cron")
        assert r.status_code == 200
        assert r.json() == {
            "status": "completed",
            "total_subscribers": 2,
            "sent": 2,
            "failed": [],
        }
        mocked.assert_awaited_once()
