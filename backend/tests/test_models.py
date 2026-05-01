from datetime import datetime, timezone
from decimal import Decimal

from app.models import AlertSubscription, FetchLog, Tender


def test_tender_model_can_be_instantiated() -> None:
    tender = Tender(
        ref_number="CPPP-PRINT-001",
        title="Book printing for government schools",
        organisation="Department of Education",
        state="Delhi",
        portal_source="cppp",
        category="printing",
        value_inr=Decimal("125000.00"),
        emd_amount=Decimal("5000.00"),
        bid_end_date=datetime(2026, 12, 31, tzinfo=timezone.utc),
        published_date=datetime(2026, 5, 1, tzinfo=timezone.utc),
        portal_url="https://example.gov.in/tender/CPPP-PRINT-001",
        keywords=["printing", "book printing"],
        relevance_score=90,
        is_active=True,
    )

    assert tender.ref_number == "CPPP-PRINT-001"
    assert tender.title == "Book printing for government schools"
    assert tender.portal_source == "cppp"
    assert "Tender" in repr(tender)


def test_alert_subscription_model_can_be_instantiated() -> None:
    subscription = AlertSubscription(
        email="printer@example.com",
        whatsapp="+919999999999",
        keywords=["printing"],
        states=["Maharashtra"],
        frequency="daily",
        is_active=True,
    )

    assert subscription.email == "printer@example.com"
    assert subscription.keywords == ["printing"]
    assert subscription.frequency == "daily"
    assert "AlertSubscription" in repr(subscription)


def test_fetch_log_model_can_be_instantiated() -> None:
    fetch_log = FetchLog(
        portal="gem",
        keyword_used="printing",
        tenders_found=12,
        new_added=4,
        status="success",
    )

    assert fetch_log.portal == "gem"
    assert fetch_log.new_added == 4
    assert fetch_log.status == "success"
    assert "FetchLog" in repr(fetch_log)
