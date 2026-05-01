from rapidfuzz import fuzz

from app.schemas import TenderCreate


def tender_fingerprint(tender: TenderCreate) -> str:
    key = f"{tender.source}:{tender.external_id}".casefold()
    return " ".join(key.split())


def deduplicate_tenders(tenders: list[TenderCreate], title_threshold: int = 94) -> list[TenderCreate]:
    seen: dict[str, TenderCreate] = {}
    unique: list[TenderCreate] = []
    for tender in tenders:
        fingerprint = tender_fingerprint(tender)
        if fingerprint in seen:
            continue
        if any(fuzz.token_set_ratio(tender.title, existing.title) >= title_threshold for existing in unique):
            continue
        seen[fingerprint] = tender
        unique.append(tender)
    return unique
