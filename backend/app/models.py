from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, Computed, DateTime, Index, Integer, Numeric, SmallInteger, String, Text, func, text
from sqlalchemy.dialects.postgresql import ARRAY, TSVECTOR
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, synonym


class Base(DeclarativeBase):
    pass


class Tender(Base):
    __tablename__ = "tenders"
    __table_args__ = (
        Index("idx_tenders_deadline", "bid_end_date"),
        Index("idx_tenders_state", "state"),
        Index("idx_tenders_portal", "portal_source"),
        Index("idx_tenders_category", "category"),
        Index("idx_tenders_fts", "search_vector", postgresql_using="gin"),
        Index("idx_tenders_keywords", "keywords", postgresql_using="gin"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ref_number: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    organisation: Mapped[str | None] = mapped_column(Text)
    state: Mapped[str | None] = mapped_column(String(60))
    portal_source: Mapped[str | None] = mapped_column(String(30))
    category: Mapped[str | None] = mapped_column(String(60))
    value_inr: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"), server_default=text("0"), nullable=True)
    emd_amount: Mapped[Decimal] = mapped_column(Numeric(15, 2), default=Decimal("0"), server_default=text("0"), nullable=True)
    bid_end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    portal_url: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    relevance_score: Mapped[int] = mapped_column(SmallInteger, default=50, server_default=text("50"), nullable=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("TRUE"), nullable=True)
    search_vector: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('english', coalesce(title,'') || ' ' || coalesce(organisation,''))",
            persisted=True,
        ),
        nullable=True,
    )

    source = synonym("portal_source")
    external_id = synonym("ref_number")
    buyer = synonym("organisation")
    estimated_value = synonym("value_inr")
    deadline = synonym("bid_end_date")
    published_at = synonym("published_date")
    tender_url = synonym("portal_url")

    def __repr__(self) -> str:
        return f"Tender(id={self.id!r}, ref_number={self.ref_number!r}, title={self.title!r})"


class AlertSubscription(Base):
    __tablename__ = "alert_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(Text, nullable=False)
    whatsapp: Mapped[str | None] = mapped_column(Text)
    keywords: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        default=lambda: ["printing"],
        server_default=text("ARRAY['printing']::TEXT[]"),
        nullable=True,
    )
    states: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text),
        default=list,
        server_default=text("ARRAY[]::TEXT[]"),
        nullable=True,
    )
    frequency: Mapped[str] = mapped_column(String(10), default="daily", server_default=text("'daily'"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("TRUE"), nullable=True)
    last_sent: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)

    def __repr__(self) -> str:
        return f"AlertSubscription(id={self.id!r}, email={self.email!r}, frequency={self.frequency!r})"


class FetchLog(Base):
    __tablename__ = "fetch_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    portal: Mapped[str | None] = mapped_column(String(30))
    keyword_used: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=True)
    tenders_found: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=True)
    new_added: Mapped[int] = mapped_column(Integer, default=0, server_default=text("0"), nullable=True)
    status: Mapped[str | None] = mapped_column(String(10))
    error_msg: Mapped[str | None] = mapped_column(Text)

    def __repr__(self) -> str:
        return f"FetchLog(id={self.id!r}, portal={self.portal!r}, status={self.status!r})"


FetchRun = FetchLog
