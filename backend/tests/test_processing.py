from app.fetchers.base import RawTender
from app.processing.deduplicator import deduplicate_tenders
from app.processing.normaliser import normalise_tender
from app.processing.tagger import tag_printing_keywords


def test_normalise_parses_dates_and_keywords() -> None:
    raw = RawTender(
        source="cppp",
        external_id="1",
        title="  Book printing for school textbooks  ",
        deadline="31 December 2026",
        keywords=["book printing", "book printing"],
    )
    tender = normalise_tender(raw)
    assert tender.title == "Book printing for school textbooks"
    assert tender.deadline is not None
    assert tender.keywords == ["book printing"]


def test_deduplicate_tenders_removes_same_external_id() -> None:
    raw = RawTender(source="cppp", external_id="1", title="Security printing of forms", keywords=["security printing"])
    tender = normalise_tender(raw)
    assert deduplicate_tenders([tender, tender]) == [tender]


def test_tagger_finds_printing_keywords() -> None:
    tags = tag_printing_keywords("Supply of toner cartridge and ink supply")
    assert tags == ["toner cartridge", "ink supply"]
