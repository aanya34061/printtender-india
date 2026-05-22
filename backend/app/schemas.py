from datetime import datetime
from decimal import Decimal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class TenderBase(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    ref_number: str = Field(validation_alias=AliasChoices("ref_number", "external_id"))
    title: str
    organisation: str | None = Field(
        default=None, validation_alias=AliasChoices("organisation", "buyer")
    )
    state: str | None = None
    portal_source: str | None = Field(
        default=None, validation_alias=AliasChoices("portal_source", "source")
    )
    category: str | None = None
    value_inr: Decimal = Field(
        default=Decimal("0"),
        validation_alias=AliasChoices("value_inr", "estimated_value"),
    )
    emd_amount: Decimal = Decimal("0")
    bid_end_date: datetime | None = Field(
        default=None, validation_alias=AliasChoices("bid_end_date", "deadline")
    )
    published_date: datetime | None = Field(
        default=None, validation_alias=AliasChoices("published_date", "published_at")
    )
    portal_url: str | None = Field(
        default=None, validation_alias=AliasChoices("portal_url", "tender_url")
    )
    tender_id: str | None = None
    link_type: str = "search"
    link_verified: bool = False
    keywords: list[str] = Field(default_factory=list)
    relevance_score: int = 50
    is_active: bool = True

    @field_validator("value_inr", "emd_amount", mode="before")
    @classmethod
    def default_numeric(cls, value: object) -> object:
        return Decimal("0") if value is None else value

    @field_validator("keywords", mode="before")
    @classmethod
    def default_keywords(cls, value: object) -> object:
        return [] if value is None else value

    @field_validator("link_type", mode="before")
    @classmethod
    def default_link_type(cls, value: object) -> str:
        text = str(value or "").strip()
        return text if text in {"direct", "deep", "search", "newspaper"} else "search"

    @property
    def external_id(self) -> str:
        return self.ref_number

    @property
    def buyer(self) -> str | None:
        return self.organisation

    @property
    def source(self) -> str | None:
        return self.portal_source

    @property
    def estimated_value(self) -> Decimal:
        return self.value_inr

    @property
    def deadline(self) -> datetime | None:
        return self.bid_end_date

    @property
    def published_at(self) -> datetime | None:
        return self.published_date

    @property
    def tender_url(self) -> str | None:
        return self.portal_url


class TenderCreate(TenderBase):
    pass


class TenderRead(TenderBase):
    model_config = ConfigDict(
        from_attributes=True, populate_by_name=True, extra="ignore"
    )

    id: int
    fetched_at: datetime | None = None


class TenderListResponse(BaseModel):
    total: int
    items: list[TenderRead]
    page: int = 1
    limit: int = 25


class AlertSubscriptionCreate(BaseModel):
    email: str
    whatsapp: str | None = None
    keywords: list[str] = Field(default_factory=lambda: ["printing"])
    states: list[str] = Field(default_factory=list)
    frequency: str = "daily"

    @field_validator("keywords", mode="before")
    @classmethod
    def default_alert_keywords(cls, value: object) -> object:
        return ["printing"] if value is None else value

    @field_validator("states", mode="before")
    @classmethod
    def default_alert_states(cls, value: object) -> object:
        return [] if value is None else value


class AlertSubscriptionRead(AlertSubscriptionCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool = True
    last_sent: datetime | None = None
    created_at: datetime | None = None


class FetchLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str | None = Field(
        default=None, validation_alias=AliasChoices("source", "portal")
    )
    keyword_used: str | None = None
    fetched_at: datetime | None = None
    tenders_found: int = 0
    new_added: int = 0
    status: str | None = None
    error_msg: str | None = None


class StatsResponse(BaseModel):
    total_active: int
    tenders_today: int
    portals_count: int
    by_portal: dict[str, int] = Field(default_factory=dict)
    by_source_category: dict[str, int] = Field(default_factory=dict)
    last_fetch: datetime | None
    keywords_tracked: int


class TenderSearchParams(BaseModel):
    q: str | None = Field(default=None, min_length=2)
    state: str | None = None
    portal: str | None = None
    days: int | None = Field(default=None, ge=1)
    category: str | None = None
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=25, ge=1, le=100)


TenderSearchResponse = TenderListResponse
AlertCreate = AlertSubscriptionCreate
AlertRead = AlertSubscriptionRead
