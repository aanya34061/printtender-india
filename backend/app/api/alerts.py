import secrets

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.email_sender import send_confirmation_email, send_welcome_email
from app.config import get_settings
from app.database import get_db
from app.models import AlertSubscription
from app.schemas import AlertSubscriptionCreate, AlertSubscriptionRead

router = APIRouter()


# ── New compact schema used by the frontend ────────────────────────────────
class _AlertCreate(BaseModel):
    email: EmailStr
    keyword: str = "printing"
    frequency: str = "daily"

    @field_validator("frequency")
    @classmethod
    def valid_frequency(cls, v: str) -> str:
        if v not in ("daily", "instant", "weekly"):
            raise ValueError("frequency must be 'daily', 'instant', or 'weekly'")
        return v


# ── Old verbose schema (kept for backwards-compat) ─────────────────────────
class _SubscribePayload(AlertSubscriptionCreate):
    email: EmailStr  # type: ignore[assignment]

    @field_validator("keywords")
    @classmethod
    def at_least_one(cls, v: list[str]) -> list[str]:
        if len(v) < 1:
            raise ValueError("At least one keyword is required")
        return v

    @field_validator("frequency")
    @classmethod
    def valid_freq(cls, v: str) -> str:
        if v not in ("daily", "weekly", "instant"):
            raise ValueError("frequency must be 'daily', 'weekly', or 'instant'")
        return v


class _DeleteBody(BaseModel):
    email: EmailStr


def _make_token() -> str:
    return secrets.token_urlsafe(32)


# ── POST /api/alerts  (new, used by frontend) ─────────────────────────────
@router.post("", status_code=201)
async def create_alert(
    payload: _AlertCreate,
    session: AsyncSession = Depends(get_db),
) -> dict:
    token = _make_token()
    alert = AlertSubscription(
        email=str(payload.email),
        keywords=[payload.keyword],
        states=[],
        frequency=payload.frequency,
        confirm_token=token,
        is_confirmed=False,
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    settings = get_settings()
    confirm_url = f"{settings.FRONTEND_URL.rstrip('/')}/confirm?token={token}"
    try:
        send_confirmation_email(str(payload.email), payload.keyword, confirm_url)
    except Exception:
        pass
    return {
        "id": alert.id,
        "email": alert.email,
        "keyword": payload.keyword,
        "frequency": alert.frequency,
        "is_confirmed": alert.is_confirmed,
        "message": "Subscription created — check your email to confirm.",
    }


# ── POST /api/alerts/subscribe  (legacy, kept for tests) ──────────────────
@router.post("/subscribe", response_model=AlertSubscriptionRead, status_code=201)
async def subscribe(
    payload: _SubscribePayload,
    session: AsyncSession = Depends(get_db),
) -> AlertSubscriptionRead:
    token = _make_token()
    alert = AlertSubscription(
        email=str(payload.email),
        whatsapp=payload.whatsapp,
        keywords=payload.keywords,
        states=payload.states,
        frequency=payload.frequency,
        confirm_token=token,
        is_confirmed=False,
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    try:
        send_welcome_email(str(payload.email), payload.keywords, payload.frequency)
    except Exception:
        pass
    return AlertSubscriptionRead.model_validate(alert)


# ── GET /api/alerts/confirm/{token} ──────────────────────────────────────
@router.get("/confirm/{token}")
async def confirm_alert(token: str, session: AsyncSession = Depends(get_db)) -> RedirectResponse:
    result = await session.execute(
        select(AlertSubscription).where(AlertSubscription.confirm_token == token)
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise HTTPException(status_code=404, detail="Confirmation token not found")
    sub.is_confirmed = True
    await session.commit()
    frontend_url = get_settings().FRONTEND_URL
    return RedirectResponse(url=f"{frontend_url}?confirmed=true", status_code=303)


# ── DELETE /api/alerts/{id} ───────────────────────────────────────────────
@router.delete("/{alert_id}", status_code=200)
async def unsubscribe(
    alert_id: int,
    body: _DeleteBody = Body(...),
    session: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    result = await session.get(AlertSubscription, alert_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    if result.email != str(body.email):
        raise HTTPException(status_code=403, detail="Email does not match this subscription")
    result.is_active = False
    await session.commit()
    return {"detail": "Unsubscribed successfully"}
