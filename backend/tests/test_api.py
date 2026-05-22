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
        title="Printing of Government Forms",
        organisation="DoPT",
        state="Delhi",
        portal_source="TOI Tenders",
        category="printing",
        value_inr=Decimal("100000"),
        emd_amount=Decimal("5000"),
        bid_end_date=datetime(2026, 6, 30, tzinfo=timezone.utc),
        published_date=datetime(2026, 4, 1, tzinfo=timezone.utc),
        portal_url="https://timesofindia.indiatimes.com/tenders/1",
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
    session.scalar.side_effect = OSError("database host not reachable")
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
        assert body["tenders"][0]["portal_source"] == "TOI Tenders"
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
        assert "mptenders.gov.in" in body["portal_url"]
    finally:
        _clear()


@pytest.mark.asyncio
async def test_get_tender_rewrites_gem_document_url_to_bid_search():
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
            "https://bidplus.gem.gov.in/all-bids?search_bid=GEM%2F2026%2FB%2F7142926"
        )
        assert body["link_type"] == "search"
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
        assert any("reference number" in s for s in steps)
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
            execute_returns=[("MP Tenders", 4), ("TOI Tenders", 2)],
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
        assert body["by_portal"] == {"MP Tenders": 4, "TOI Tenders": 2}
        assert body["portals_count"] == 2
    finally:
        _clear()


@pytest.mark.asyncio
async def test_get_stats_merges_state_mh_into_maharashtra_tenders():
    _override_db(
        _make_session(
            scalar_returns=[3, 0, 0, 0, 1, datetime(2026, 5, 1, tzinfo=timezone.utc)],
            scalars_returns=[["printing"]],
            execute_returns=[("State-MH", 2), ("Maharashtra Tenders", 1)],
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
    with patch("app.api.alerts.send_welcome_email"):
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
    with patch("app.api.fetch.run_fetch_cycle", new=AsyncMock(return_value=5)):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.post("/api/fetch/trigger")
        assert r.status_code == 200
        assert r.json()["status"] == "triggered"
