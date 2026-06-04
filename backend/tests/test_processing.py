from datetime import datetime, timedelta, timezone

import pandas as pd

from app.processing.deduplicator import deduplicate
from app.processing.normaliser import normalise, normalise_tender, parse_bid_end_date
from app.processing.tagger import pipeline, tag_category


def raw_record(
    ref_number: str,
    title: str,
    *,
    state: str = "MP",
    value_raw: str = "1000",
    deadline_raw: str | None = None,
    portal_source: str = "CPPP",
    portal_url: str = "https://eprocure.gov.in/tender",
    tender_id: str | None = None,
    link_type: str = "deep",
    link_verified: bool = False,
    fetched_at: str = "2026-05-01T00:00:00+00:00",
) -> dict:
    return {
        "ref_number": ref_number,
        "title": title,
        "organisation": " Directorate of Printing ",
        "state": state,
        "portal_source": portal_source,
        "deadline_raw": deadline_raw or future_deadline(),
        "value_raw": value_raw,
        "portal_url": portal_url,
        "tender_id": tender_id,
        "link_type": link_type,
        "link_verified": link_verified,
        "keyword_hit": "printing",
        "fetched_at": fetched_at,
    }


def future_deadline() -> str:
    return (datetime.now(timezone.utc) + timedelta(days=30)).strftime("%d %B %Y")


def past_deadline() -> str:
    return (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%d %B %Y")


def test_normaliser_value_parsing() -> None:
    df = normalise(
        [
            raw_record("A", "Book printing", value_raw="2.5 Lakh"),
            raw_record("B", "Answer books printing", value_raw="1 Crore"),
            raw_record("C", "Digital printing", value_raw="₹ 45,000"),
            raw_record("D", "Paper printing posted 8 May ₹3.6 L GEM service", value_raw=""),
        ]
    )

    assert df["value_inr"].tolist() == [250000.0, 10000000.0, 45000.0, 360000.0]


def test_normalise_tender_extracts_value_embedded_in_heading() -> None:
    tender = normalise_tender(
        raw_record(
            "TERMS",
            "Paper-based Printing Services posted 8 May ₹3.6 L GEM Service",
            value_raw="",
            portal_source="TenderDekho",
            portal_url="https://example.com/tender",
        )
    )

    assert tender is not None
    assert tender.value_inr == 360000.0


def test_normaliser_state_mapping() -> None:
    df = normalise([raw_record("A", "Book printing", state="MP")])

    assert df.iloc[0]["state"] == "Madhya Pradesh"


def test_normaliser_preserves_link_metadata() -> None:
    df = normalise(
        [
            raw_record(
                "A",
                "Book printing",
                portal_url="https://eprocure.gov.in/eprocure/app?component=%24DirectLink&page=FrontEndTendersByNIT&service=direct&session=T&sp=S12345678",
                tender_id="S12345678",
                link_verified=True,
            )
        ]
    )

    assert df.iloc[0]["tender_id"] == "S12345678"
    assert df.iloc[0]["link_type"] == "deep"
    assert bool(df.iloc[0]["link_verified"]) is True


def test_normalise_tender_accepts_fetcher_dict() -> None:
    tender = normalise_tender(
        raw_record(
            "A",
            "Book printing",
            value_raw="2.5 Lakh",
            portal_url="https://eprocure.gov.in/eprocure/app?component=%24DirectLink&page=FrontEndTendersByNIT&service=direct&session=T&sp=S12345678",
            tender_id="S12345678",
            link_verified=True,
        )
    )

    assert tender.ref_number == "A"
    assert tender.value_inr == 250000.0
    assert tender.tender_id == "S12345678"
    assert tender.link_type == "deep"
    assert tender.link_verified is True


def test_normalise_tender_accepts_tracked_print_keyword_without_product_keyword() -> None:
    tender = normalise_tender(
        raw_record(
            "A",
            "Offset printing work",
            portal_url="https://example.com/tender/A",
        )
    )

    assert tender is not None
    assert "offset printing" in tender.keywords


def test_normalise_tender_drops_generic_printing_term_without_tracked_keyword() -> None:
    tender = normalise_tender(
        raw_record(
            "A",
            "Printing work",
            portal_url="https://example.com/tender/A",
        )
    )

    assert tender is None


def test_normalise_tender_drops_non_printing_result_even_if_keyword_was_used() -> None:
    tender = normalise_tender(
        raw_record(
            "A",
            "Construction of staff quarters",
            portal_url="https://example.com/tender/A",
        )
    )

    assert tender is None


def test_normalise_tender_drops_result_when_keyword_hit_is_not_in_tender_text() -> None:
    tender = normalise_tender(
        raw_record(
            "A",
            "Directorate of Health Services Tender - MP Tender",
            portal_url="https://example.com/tender/A",
        )
    )

    assert tender is None


def test_normalise_tender_drops_file_number_construction_false_positive() -> None:
    tender = normalise_tender(
        raw_record(
            "MPGMC/77/26X3/3/JAN/2026-27",
            "Construction of Community Hall and Toilet Repairs Work. Ward 09. Zone 02 File No. 77/26X3/3.",
            portal_url="https://example.com/tender/A",
        )
    )

    assert tender is None


def test_normalise_tender_drops_medical_card_capacity_false_positive() -> None:
    tender = normalise_tender(
        raw_record(
            "AIIMSBBN/PROC/2026-27/PAC",
            "Automated System for Bacterial Identification and Sensitivity VITEK 2 Compact 60 Card Capacity",
            portal_url="https://example.com/tender/A",
        )
        | {"organisation": "All India Institute of Medical Sciences"}
    )

    assert tender is None


def test_normalise_tender_drops_probe_card_false_positive() -> None:
    tender = normalise_tender(
        raw_record(
            "45190",
            "Rate contract for the assembly of Epoxy Probe Cards for two years",
            portal_url="https://example.com/tender/A",
        )
        | {"organisation": "Semi-Conductor Laboratory"}
    )

    assert tender is None


def test_normalise_tender_drops_library_book_supply_false_positive() -> None:
    tender = normalise_tender(
        raw_record(
            "NEIGR/SP/EMP-01/2026-27",
            "Empanelment for supply of Library Books/Journals",
            portal_url="https://example.com/tender/A",
        )
        | {"organisation": "Store and Procurement Section"}
    )

    assert tender is None


def test_normalise_tender_drops_digital_evaluation_answer_book_false_positive() -> None:
    tender = normalise_tender(
        raw_record(
            "373/STORE/BU/2026",
            "Tender for digital evaluation system of answer books",
            portal_url="https://example.com/tender/A",
        )
        | {"organisation": "Barkatullah University"}
    )

    assert tender is None


def test_normalise_tender_drops_stationery_used_as_location() -> None:
    tender = normalise_tender(
        raw_record(
            "3064",
            "Construction of bitumen road from Kapil Stationery to Kunbi Patel Dharmshala",
            portal_url="https://example.com/tender/A",
        )
        | {"organisation": "Urban Administration and Development"}
    )

    assert tender is None


def test_normalise_tender_keeps_printed_file_covers() -> None:
    tender = normalise_tender(
        raw_record(
            "CGM/BR/ENQ-34",
            "Supply of Printed File Covers",
            portal_url="https://example.com/tender/A",
        )
    )

    assert tender is not None
    assert "files" in tender.keywords


def test_normalise_tender_uses_organisation_and_ref_for_keyword_matching() -> None:
    tender = normalise_tender(
        raw_record(
            "ANSWER-BOOK-001",
            "Annual rate contract",
            portal_url="https://example.com/tender/A",
        )
        | {"organisation": "Directorate of Answer Book Printing"}
    )

    assert tender is not None
    assert "answer books" in tender.keywords


def test_normalise_tender_keeps_lic_active_without_deadline() -> None:
    raw = raw_record(
        "LIC-STATIONERY-001",
        "Annual contract for supply of stationery and book items",
        portal_source="LIC Tenders",
        portal_url="https://licindia.in/tender",
    )
    raw["deadline_raw"] = ""

    tender = normalise_tender(
        raw
    )

    assert tender is not None
    assert tender.bid_end_date is None
    assert tender.is_active is True


def test_normaliser_drops_past_deadline_records() -> None:
    df = normalise(
        [
            raw_record("OLD", "Book printing", deadline_raw=past_deadline()),
            raw_record("NEW", "Book printing", deadline_raw=future_deadline()),
        ]
    )

    assert df["ref_number"].tolist() == ["NEW"]


def test_parse_bid_end_date_uses_end_of_day_for_date_only_inputs() -> None:
    parsed = parse_bid_end_date("22 May 2026")

    assert parsed is not None
    assert parsed.isoformat() == "2026-05-22T18:29:59+00:00"


def test_normaliser_drops_non_printing_rows() -> None:
    df = normalise(
        [
            raw_record("A", "Construction of boundary wall"),
            raw_record("B", "Book printing for schools"),
        ]
    )

    assert df["ref_number"].tolist() == ["B"]


def test_deduplicator_removes_exact_ref_number_duplicates() -> None:
    df = pd.DataFrame(
        [
            {
                "ref_number": "A",
                "title": "Book Printing",
                "portal_source": "CPPP",
                "fetched_at": "2026-05-01T00:00:00+00:00",
            },
            {
                "ref_number": "A",
                "title": "Book Printing",
                "portal_source": "CPPP",
                "fetched_at": "2026-05-01T00:01:00+00:00",
            },
        ]
    )

    deduped = deduplicate(df)

    assert len(deduped) == 1
    assert deduped.iloc[0]["ref_number"] == "A"


def test_deduplicator_removes_fuzzy_title_duplicates() -> None:
    df = pd.DataFrame(
        [
            {
                "ref_number": "A",
                "title": "Offset Printing Of Forms",
                "portal_source": "CPPP",
                "fetched_at": "2026-05-01T00:05:00+00:00",
            },
            {
                "ref_number": "B",
                "title": "offset printing of forms",
                "portal_source": "CPPP",
                "fetched_at": "2026-05-01T00:01:00+00:00",
            },
        ]
    )

    deduped = deduplicate(df)

    assert len(deduped) == 1
    assert deduped.iloc[0]["ref_number"] == "B"


def test_tagger_offset_printing() -> None:
    assert tag_category("Supply of Offset Printing Paper") == "Offset Printing"


def test_tagger_consumables() -> None:
    assert tag_category("Purchase of Toner Cartridge") == "Consumables"


def test_pipeline_dedupes_and_sets_category() -> None:
    raw = [
        raw_record("A", "Supply of Offset Printing Paper", value_raw="2.5 Lakh"),
        raw_record("A", "Supply of Offset Printing Paper", value_raw="2.5 Lakh"),
        raw_record("B", "supply of offset printing paper", value_raw="2.5 Lakh"),
        raw_record("C", "Purchase of Toner Cartridge", value_raw="₹ 45,000"),
        raw_record("D", "Book printing for school textbooks"),
        raw_record("E", "Banner printing for public campaign"),
        raw_record("F", "Stationery printing of letterhead"),
        raw_record("G", "Packaging label printing"),
        raw_record("H", "Digital print of certificates"),
        raw_record("I", "Security printing of ballot paper"),
    ]

    result = pipeline(raw)

    assert len(result) < 10
    assert all(record["category"] for record in result)
