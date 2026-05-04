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
        portal_source="CPPP",
        category="printing",
        value_inr=Decimal("100000"),
        emd_amount=Decimal("5000"),
        bid_end_date=datetime(2026, 6, 30, tzinfo=timezone.utc),
        published_date=datetime(2026, 4, 1, tzinfo=timezone.utc),
        portal_url="https://eprocure.gov.in/tender/1",
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
                "/api/tenders?q=printing&state=Delhi&portal=CPPP&deadline_within_days=7"
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
async def test_get_tender_replaces_generic_homepage_link():
    row = _make_tender_row(
        ref_number="CPPP/2025/04/123",
        portal_url="https://eprocure.gov.in/",
        tender_id="S12345678",
        link_verified=False,
    )
    _override_db(_make_session(get_returns=row))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders/1")
        body = r.json()
        assert body["link_type"] == "deep"
        assert "sp=S12345678" in body["portal_url"]
    finally:
        _clear()


@pytest.mark.asyncio
async def test_get_tender_apply_steps_cppp():
    row = _make_tender_row(portal_source="CPPP")
    _override_db(_make_session(get_returns=row))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders/1")
        steps = r.json()["apply_steps"]
        assert any("eprocure" in s for s in steps)
    finally:
        _clear()


@pytest.mark.asyncio
async def test_get_tender_apply_steps_gem():
    row = _make_tender_row(portal_source="GeM")
    _override_db(_make_session(get_returns=row))
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            r = await c.get("/api/tenders/1")
        steps = r.json()["apply_steps"]
        assert any("gem.gov.in" in s for s in steps)
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
            execute_returns=[],
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
        ):
            assert key in body, f"missing key: {key}"
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
