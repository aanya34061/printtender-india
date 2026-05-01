from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models import AlertSubscription
from app.schemas import AlertSubscriptionCreate, AlertSubscriptionRead

router = APIRouter()


@router.post("", response_model=AlertSubscriptionRead, status_code=201)
async def create_alert(payload: AlertSubscriptionCreate, session: AsyncSession = Depends(get_db)) -> AlertSubscriptionRead:
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
    return AlertSubscriptionRead.model_validate(alert)
