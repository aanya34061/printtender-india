from __future__ import annotations

import secrets
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Body, Depends, Header, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import delete, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.concurrency import run_in_threadpool

from app.config import get_settings
from app.database import get_db
from app.email_service import (
    send_all_categories_email,
    send_confirmation_email,
    send_test_tender_email,
    send_unsubscribe_confirmation_email,
)
from app.models import AlertSubscription
from app.models import Tender
from app.processing.relevance import build_printing_relevance_predicate
from app.schemas import AlertSubscriptionCreate, AlertSubscriptionRead
from app.sources import ACTIVE_TENDER_SOURCES

router = APIRouter()


class _AlertCreate(BaseModel):
    email: EmailStr
    keyword: str = "printing"
    frequency: str = "daily"

    @field_validator("keyword")
    @classmethod
    def valid_keyword(cls, value: str) -> str:
        keyword = " ".join(value.split())
        if not keyword:
            raise ValueError("keyword is required")
        return keyword

    @field_validator("frequency")
    @classmethod
    def valid_frequency(cls, value: str) -> str:
        if value not in ("daily", "instant"):
            raise ValueError("frequency must be 'daily' or 'instant'")
        return value


class _SubscribePayload(AlertSubscriptionCreate):
    email: EmailStr  # type: ignore[assignment]

    @field_validator("keywords")
    @classmethod
    def at_least_one(cls, value: list[str]) -> list[str]:
        if len(value) < 1:
            raise ValueError("At least one keyword is required")
        return value

    @field_validator("frequency")
    @classmethod
    def valid_freq(cls, value: str) -> str:
        if value not in ("daily", "weekly", "instant"):
            raise ValueError("frequency must be 'daily', 'weekly', or 'instant'")
        return value


class _DeleteBody(BaseModel):
    email: EmailStr | None = None


def _make_token() -> str:
    return secrets.token_urlsafe(32)


def _require_admin(authorization: str | None) -> None:
    expected = get_settings().CRON_SECRET
    if not expected:
        raise HTTPException(status_code=503, detail="CRON_SECRET is not configured")
    if expected and authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Unauthorized")


@router.post("", status_code=201)
async def create_alert(
    payload: _AlertCreate,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    token = _make_token()
    email = str(payload.email)
    result = await session.execute(
        select(AlertSubscription).where(
            AlertSubscription.email == email,
            AlertSubscription.keyword == payload.keyword,
        )
    )
    alert = result.scalar_one_or_none()
    if alert is None:
        alert = AlertSubscription(
            email=email,
            keyword=payload.keyword,
            keywords=[payload.keyword],
            states=[],
            frequency=payload.frequency,
            token=token,
            confirm_token=token,
            confirmed=False,
            is_confirmed=False,
            is_active=True,
        )
        session.add(alert)
    else:
        alert.frequency = payload.frequency
        alert.keywords = [payload.keyword]
        alert.token = token
        alert.confirm_token = token
        alert.confirmed = False
        alert.is_confirmed = False
        alert.confirmed_at = None
        alert.is_active = True
    await session.commit()

    confirm_url = f"{get_settings().BACKEND_URL.rstrip('/')}/api/alerts/confirm/{token}"
    background_tasks.add_task(
        send_confirmation_email, email, payload.keyword, confirm_url
    )
    return {"status": "pending", "message": "Check your email to confirm the alert."}


@router.post("/subscribe", response_model=AlertSubscriptionRead, status_code=201)
async def subscribe(
    payload: _SubscribePayload,
    session: AsyncSession = Depends(get_db),
) -> AlertSubscriptionRead:
    token = _make_token()
    primary_keyword = payload.keywords[0]
    email = str(payload.email)
    result = await session.execute(
        select(AlertSubscription).where(
            AlertSubscription.email == email,
            AlertSubscription.keyword == primary_keyword,
        )
    )
    alert = result.scalar_one_or_none()
    if not isinstance(alert, AlertSubscription):
        alert = AlertSubscription(
            email=email,
            keyword=primary_keyword,
            whatsapp=payload.whatsapp,
            keywords=payload.keywords,
            states=payload.states,
            frequency=payload.frequency,
            token=token,
            confirm_token=token,
            confirmed=False,
            is_confirmed=False,
            is_active=True,
        )
        session.add(alert)
    else:
        alert.whatsapp = payload.whatsapp
        alert.keywords = payload.keywords
        alert.states = payload.states
        alert.frequency = payload.frequency
        alert.token = token
        alert.confirm_token = token
        alert.confirmed = False
        alert.is_confirmed = False
        alert.confirmed_at = None
        alert.is_active = True

    await session.commit()
    await session.refresh(alert)
    confirm_url = f"{get_settings().BACKEND_URL.rstrip('/')}/api/alerts/confirm/{token}"
    confirmation_sent = await run_in_threadpool(
        send_confirmation_email,
        email,
        ", ".join(payload.keywords),
        confirm_url,
    )
    test_sent = await run_in_threadpool(send_test_tender_email, email, payload.keywords)
    if not confirmation_sent or not test_sent:
        raise HTTPException(
            status_code=502,
            detail="Subscription was saved, but email delivery failed. Check RESEND_API_KEY and EMAIL_FROM.",
        )
    return AlertSubscriptionRead.model_validate(alert)


@router.post("/send-test")
async def send_test_to_subscribers(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    _require_admin(authorization)
    result = await session.scalars(
        select(AlertSubscription).where(AlertSubscription.is_active.is_(True))
    )
    subscribers = list(result)
    sent = 0
    failed: list[str] = []

    for subscriber in subscribers:
        keywords = subscriber.keywords or [subscriber.keyword or "printing"]
        ok = await run_in_threadpool(
            send_test_tender_email,
            subscriber.email,
            keywords,
        )
        if ok:
            sent += 1
        else:
            failed.append(subscriber.email)

    return {
        "status": "completed",
        "total_subscribers": len(subscribers),
        "sent": sent,
        "failed": failed,
    }


@router.post("/send-categories")
async def send_categories_to_subscribers(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
) -> dict[str, object]:
    _require_admin(authorization)
    result = await session.scalars(
        select(AlertSubscription).where(AlertSubscription.is_active.is_(True))
    )
    subscribers = list(result)
    tender_rows = await session.scalars(
        select(Tender)
        .where(Tender.is_active.is_(True))
        .where(Tender.portal_source.in_(ACTIVE_TENDER_SOURCES))
        .where(Tender.bid_end_date > datetime.now(timezone.utc))
        .where(build_printing_relevance_predicate(Tender))
        .order_by(Tender.fetched_at.desc().nulls_last(), Tender.id.desc())
        .limit(3)
    )
    tenders = list(tender_rows)
    sent = 0
    failed: list[str] = []

    for subscriber in subscribers:
        ok = await run_in_threadpool(send_all_categories_email, subscriber.email, tenders)
        if ok:
            sent += 1
        else:
            failed.append(subscriber.email)

    return {
        "status": "completed",
        "total_subscribers": len(subscribers),
        "sent": sent,
        "failed": failed,
    }


@router.get("/confirm/{token}")
async def confirm_alert(
    token: str, session: AsyncSession = Depends(get_db)
) -> RedirectResponse:
    result = await session.execute(
        select(AlertSubscription).where(
            or_(
                AlertSubscription.token == token,
                AlertSubscription.confirm_token == token,
            )
        )
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="Confirmation token not found")
    now = datetime.now(timezone.utc)
    sub.confirmed = True
    sub.is_confirmed = True
    sub.confirmed_at = now
    sub.is_active = True
    await session.commit()
    frontend_url = get_settings().FRONTEND_URL.rstrip("/")
    return RedirectResponse(url=f"{frontend_url}?confirmed=true", status_code=303)


@router.delete("/{token}", status_code=200)
async def unsubscribe(
    token: str,
    background_tasks: BackgroundTasks,
    body: _DeleteBody | None = Body(default=None),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    result = await session.execute(
        select(AlertSubscription).where(
            or_(
                AlertSubscription.token == token,
                AlertSubscription.confirm_token == token,
            )
        )
    )
    sub = result.scalar_one_or_none()

    if sub is None and token.isdigit() and body and body.email:
        sub = await session.get(AlertSubscription, int(token))
        if sub is not None and sub.email != str(body.email):
            raise HTTPException(
                status_code=403, detail="Email does not match this subscription"
            )

    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")

    email = sub.email
    keyword = sub.keyword
    await session.execute(
        delete(AlertSubscription).where(AlertSubscription.id == sub.id)
    )
    await session.commit()
    background_tasks.add_task(send_unsubscribe_confirmation_email, email, keyword)
    return {"detail": "Unsubscribed successfully"}
