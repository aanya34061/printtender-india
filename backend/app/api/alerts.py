from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts.email_sender import send_welcome_email
from app.database import get_db
from app.models import AlertSubscription
from app.schemas import AlertSubscriptionCreate, AlertSubscriptionRead

router = APIRouter()


class _SubscribePayload(AlertSubscriptionCreate):
    email: EmailStr  # type: ignore[assignment]

    @field_validator("keywords")
    @classmethod
    def at_least_one_keyword(cls, v: list[str]) -> list[str]:
        if len(v) < 1:
            raise ValueError("At least one keyword is required")
        return v

    @field_validator("frequency")
    @classmethod
    def valid_frequency(cls, v: str) -> str:
        if v not in ("daily", "weekly"):
            raise ValueError("frequency must be 'daily' or 'weekly'")
        return v


class _DeleteBody(BaseModel):
    email: EmailStr


@router.post("/subscribe", response_model=AlertSubscriptionRead, status_code=201)
async def subscribe(
    payload: _SubscribePayload,
    session: AsyncSession = Depends(get_db),
) -> AlertSubscriptionRead:
    alert = AlertSubscription(
        email=str(payload.email),
        whatsapp=payload.whatsapp,
        keywords=payload.keywords,
        states=payload.states,
        frequency=payload.frequency,
    )
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    try:
        send_welcome_email(str(payload.email), payload.keywords, payload.frequency)
    except Exception:
        pass  # email failure must not break subscription
    return AlertSubscriptionRead.model_validate(alert)


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
