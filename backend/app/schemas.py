from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class TenderBase(BaseModel):
    source: str
    external_id: str
    title: str
    buyer: str | None = None
    state: str | None = None
    category: str | None = None
    estimated_value: float | None = None
    deadline: datetime | None = None
    published_at: datetime | None = None
    tender_url: str | None = None
    keywords: list[str] = Field(default_factory=list)


class TenderCreate(TenderBase):
    raw_payload: dict = Field(default_factory=dict)


class TenderRead(TenderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class TenderSearchResponse(BaseModel):
    total: int
    items: list[TenderRead]


class AlertCreate(BaseModel):
    email: str
    keywords: list[str] = Field(default_factory=list)
    states: list[str] = Field(default_factory=list)


class AlertRead(AlertCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    created_at: datetime


class StatsRead(BaseModel):
    total_tenders: int
    active_tenders: int
    sources: dict[str, int]
    states: dict[str, int]
