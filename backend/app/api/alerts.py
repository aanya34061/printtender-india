from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.models import AlertSubscription
from app.schemas import AlertCreate, AlertRead

router = APIRouter()


@router.post("", response_model=AlertRead, status_code=201)
async def create_alert(payload: AlertCreate, session: AsyncSession = Depends(get_session)) -> AlertRead:
    alert = AlertSubscription(email=str(payload.email), keywords=payload.keywords, states=payload.states)
    session.add(alert)
    await session.commit()
    await session.refresh(alert)
    return AlertRead.model_validate(alert)
