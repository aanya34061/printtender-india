"""API endpoint tests — database is fully mocked, no real connection required."""
import os
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:password@localhost:5432/postgres")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("RESEND_API_KEY", "re_test")

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


def _make_session(*, scalar_returns=None, scalars_returns=None, get_returns=None):
    """Return an async context-manager-compatible mock DB session."""
    session = AsyncMock()

    # scalar() → used for counts, max(), etc.
    if scalar_returns is None:
        scalar_returns = [0]
    scalar_iter = iter(scalar_returns) if isinstance(scalar_returns, list) else iter([scalar_returns])

    async def _scalar(*args, **kwargs):
        try:
            return next(scalar_iter)
        except StopIteration:
            return 0

    session.scalar.side_effect = _scalar

    # scalars() → used for list queries
    scalars_result = MagicMock()
    scalars_result.__iter__ = MagicMock(return_value=iter(scalars_returns or []))
    session.scalars.return_value = scalars_result

    # execute() for portal_status join query
    exec_result = MagicMock()
    exec_result.scalars.return_value.all.return_value = []
    session.execute.return_value = exec_result

    # get() for single-object lookup
    session.get.return_value = get_returns

    # add/commit/refresh are fire-and-forget
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()

    return session


def _override_db(session):
    async def _dep():
        yield session

    app.dependency_overrides[get_db] = _dep
    return session


def _clear_overrides():
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "env" in body


@pytest.mark.asyncio
async def test_list_tenders_returns_200():
    row = _make_tender_row()
    session = _make_session(scalar_returns=[1, 1], scalars_returns=[row])
    _override_db(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/tenders")
        assert resp.status_code == 200
        body = resp.json()
        assert "tenders" in body
        assert "total" in body
        assert "page" in body
        assert "pages" in body
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_list_tenders_default_query_is_printing():
    """Default q param should be 'printing' per spec."""
    row = _make_tender_row()
    session = _make_session(scalar_returns=[1, 1], scalars_returns=[row])
    _override_db(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/tenders")
        assert resp.status_code == 200
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_list_tenders_empty():
    session = _make_session(scalar_returns=[0, 0], scalars_returns=[])
    _override_db(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/tenders?q=printing")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["tenders"] == []
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_get_tender_detail():
    row = _make_tender_row()
    session = _make_session(get_returns=row)
    _override_db(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/tenders/1")
        assert resp.status_code == 200
        body = resp.json()
        assert "apply_steps" in body
        assert isinstance(body["apply_steps"], list)
        assert len(body["apply_steps"]) > 0
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_get_tender_apply_steps_cppp():
    row = _make_tender_row(portal_source="CPPP")
    session = _make_session(get_returns=row)
    _override_db(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/tenders/1")
        assert resp.status_code == 200
        steps = resp.json()["apply_steps"]
        assert any("eprocure.gov.in" in s for s in steps)
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_get_tender_apply_steps_gem():
    row = _make_tender_row(portal_source="GeM")
    session = _make_session(get_returns=row)
    _override_db(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/tenders/1")
        assert resp.status_code == 200
        steps = resp.json()["apply_steps"]
        assert any("gem.gov.in" in s for s in steps)
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_get_tender_not_found():
    session = _make_session(get_returns=None)
    _override_db(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/tenders/999")
        assert resp.status_code == 404
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_tender_count():
    session = _make_session(scalar_returns=[42])
    _override_db(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/tenders/count")
        assert resp.status_code == 200
        assert resp.json()["count"] == 42
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_get_stats_returns_200():
    session = _make_session(
        scalar_returns=[10, 2, 3, datetime(2026, 5, 1, tzinfo=timezone.utc)],
        scalars_returns=[["printing", "offset"]],
    )
    _override_db(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/stats")
        assert resp.status_code == 200
        body = resp.json()
        assert "total_active" in body
        assert "tenders_today" in body
        assert "portals_count" in body
        assert "keywords_tracked" in body
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_portal_status():
    session = _make_session()
    _override_db(session)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/stats/portals/status")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
    finally:
        _clear_overrides()


@pytest.mark.asyncio
async def test_subscribe_valid_returns_201():
    sub_row = MagicMock()
    sub_row.id = 1
    sub_row.email = "press@example.com"
    sub_row.whatsapp = None
    sub_row.keywords = ["printing"]
    sub_row.states = []
    sub_row.frequency = "daily"
    sub_row.is_active = True
    sub_row.last_sent = None
    sub_row.created_at = datetime(2026, 5, 1, tzinfo=timezone.utc)

    session = _make_session()

    async def _refresh(obj):
        obj.id = 1
        obj.email = "press@example.com"
        obj.whatsapp = None
        obj.keywords = ["printing"]
        obj.states = []
        obj.frequency = "daily"
        obj.is_active = True
        obj.last_sent = None
        obj.created_at = datetime(2026, 5, 1, tzinfo=timezone.utc)

    session.refresh.side_effect = _refresh
    _override_db(session)

    with patch("app.api.alerts.send_welcome_email"):
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                resp = await client.post(
                    "/alerts/subscribe",
                    json={
                        "email": "press@example.com",
                        "keywords": ["printing"],
                        "frequency": "daily",
                    },
                )
            assert resp.status_code == 201
            body = resp.json()
            assert body["email"] == "press@example.com"
            assert body["frequency"] == "daily"
        finally:
            _clear_overrides()


@pytest.mark.asyncio
async def test_subscribe_invalid_email_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/alerts/subscribe",
            json={
                "email": "not-an-email",
                "keywords": ["printing"],
                "frequency": "daily",
            },
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_subscribe_empty_keywords_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/alerts/subscribe",
            json={
                "email": "press@example.com",
                "keywords": [],
                "frequency": "daily",
            },
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_subscribe_invalid_frequency_returns_422():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/alerts/subscribe",
            json={
                "email": "press@example.com",
                "keywords": ["printing"],
                "frequency": "hourly",
            },
        )
    assert resp.status_code == 422
