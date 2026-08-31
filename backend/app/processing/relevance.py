from __future__ import annotations

import re
from typing import Iterable

from sqlalchemy import Text, and_, cast, or_
from sqlalchemy.dialects.postgresql import ARRAY, array

from app.keywords import PRINT_KEYWORDS


PRINT_SERVICE_TERMS: tuple[str, ...] = (
    "printing",
    "printing service",
    "printing services",
    "printing work",
    "offset printing",
    "digital printing",
    "security printing",
    "government forms printing",
    "textbook printing",
    "gazette printing",
    "packaging printing",
    "label printing",
    "flex printing",
    "screen printing",
    "book binding",
    "letterpress",
    "lamination",
    "printing and supply",
    "supply and printing",
    "printed",
    "printer",
    "newspaper advertisement",
    "display advertisement",
    "advertisement",
    "advertisements",
    "publication",
    "publishing",
    "public notice",
    "tender notice",
    "मुद्रण",
    "छपाई",
    "प्रकाशन",
    "विज्ञापन",
    "सूचना",
    "समाचार पत्र",
)

PRODUCT_CONTEXT_TERMS: tuple[str, ...] = (
    "supply",
    "purchase",
    "procurement",
    "rate contract",
    "annual contract",
    "empanelment",
    "manufacturer",
    "manufacturing",
    "design",
    "layout",
    "publication",
    "printing",
    "printed",
)

PRODUCT_TERMS: tuple[str, ...] = (
    "calendar",
    "diary",
    "sticker",
    "register",
    "book",
    "form",
    "paper",
    "notebook",
    "note book",
    "brochure",
    "flyer",
    "visiting card",
    "certificate",
    "receipt book",
    "prospectus",
    "catalogue",
    "pass book",
    "duplex box",
    "card",
    "answer book",
    "exercise book",
    "tag",
    "poster",
    "banner",
    "label",
    "desk pad",
    "envelope",
    "marks sheet",
    "stationary",
    "stationery",
    "note sheet",
    "file cover",
    "file covers",
    "pamphlet",
    "annual report",
    "souvenir",
)

CIVIL_WORK_TERMS: tuple[str, ...] = (
    "construction of",
    "construction work",
    "c.c. road",
    "cc road",
    "bitumen road",
    "drain work",
    "community hall",
    "urinal",
    "tubewell",
    "repair of road",
    "road portion",
)

NON_PRINT_PRODUCT_TERMS: tuple[str, ...] = (
    "probe card",
    "probe cards",
    "card capacity",
    "network card",
    "network cards",
    "memory card",
    "memory cards",
    "sd card",
    "syphilis card",
    "dengue card",
    "pabx",
    "cctv",
    "cctv systems",
    "real estate",
    "ssl certificate",
    "ssl certificates",
    "groceries",
    "ration",
    "stationary battery",
    "stationary batteries",
    "stationary engine",
    "stationary engines",
    "stationary generator",
    "stationary generators",
    "stationary pump",
    "stationary pumps",
    "stationary crane",
    "stationary lead-acid",
    "stationary vrla",
    "library books",
    "library book",
    "books/journals",
    "book/journal",
    "digital evaluation",
    "evaluation system",
    "click here to re-login",
    "eprocurement system",
    "hindi news",
)

AMBIGUOUS_KEYWORDS: frozenset[str] = frozenset(
    {
        "book",
        "books",
        "card",
        "cards",
        "file",
        "files",
        "paper",
        "papers",
        "souvenir",
        "souvenirs",
    }
)


def contains_phrase(text: str, phrase: str) -> bool:
    normalized = " ".join((text or "").casefold().split())
    term = " ".join((phrase or "").casefold().split())
    if not normalized or not term:
        return False
    if any(ord(char) > 127 for char in term):
        return term in normalized
    escaped = re.escape(term).replace(r"\ ", r"\s+")
    pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
    return re.search(pattern, normalized) is not None


def keyword_variants(keyword: str) -> tuple[str, ...]:
    term = " ".join(keyword.casefold().split())
    if not term:
        return ()
    variants = [term]
    if term.endswith("s") and len(term) > 3:
        variants.append(term[:-1])
    return tuple(dict.fromkeys(variants))


def matched_print_keywords(text: str, keyword_hit: object = None) -> set[str]:
    keywords = {
        keyword
        for keyword in PRINT_KEYWORDS
        if any(contains_phrase(text, variant) for variant in keyword_variants(keyword))
    }
    hit = str(keyword_hit or "").strip()
    if hit in PRINT_KEYWORDS and any(
        contains_phrase(text, variant) for variant in keyword_variants(hit)
    ):
        keywords.add(hit)
    return keywords


def is_printing_relevant_text(text: str, keywords: Iterable[str] | None = None) -> bool:
    normalized = " ".join((text or "").casefold().split())
    if not normalized or len(normalized) < 6:
        return False
    if any(
        noise in normalized
        for noise in (
            "click here to re-login",
            "eprocurement system government",
            "hindi news",
            "your session in the client area has expired",
        )
    ):
        return False

    matched = set(keywords or matched_print_keywords(text))
    if not matched:
        return False
    has_print_service = any(contains_phrase(text, term) for term in PRINT_SERVICE_TERMS)
    has_product = any(contains_phrase(text, term) for term in PRODUCT_TERMS) or any(
        keyword in PRINT_KEYWORDS and keyword not in PRINT_SERVICE_TERMS
        for keyword in matched
    )
    has_context = any(contains_phrase(text, term) for term in PRODUCT_CONTEXT_TERMS)
    has_civil_work = any(contains_phrase(text, term) for term in CIVIL_WORK_TERMS)
    has_non_print_product = any(
        contains_phrase(text, term) for term in NON_PRINT_PRODUCT_TERMS
    )
    if has_civil_work or has_non_print_product:
        return False
    if has_print_service:
        return True
    return has_product and has_context


def extract_relevant_print_keywords(
    *,
    title: str,
    organisation: str | None = None,
    ref_number: str | None = None,
    keyword_hit: object = None,
) -> set[str]:
    text = " ".join(
        part.strip()
        for part in (title or "", organisation or "", ref_number or "")
        if part and part.strip()
    )
    keywords = matched_print_keywords(text, keyword_hit)
    if not is_printing_relevant_text(text, keywords):
        return set()
    return keywords


def build_printing_relevance_predicate(model):
    text_columns = (model.title, model.organisation, model.ref_number)

    def any_ilike(terms: tuple[str, ...]):
        return or_(
            *[
                column.ilike(f"%{term}%")
                for term in terms
                for column in text_columns
            ]
        )

    product_keywords = tuple(
        sorted(
            {
                keyword
                for keyword in PRINT_KEYWORDS
                if keyword not in PRINT_SERVICE_TERMS
                and keyword.casefold() not in AMBIGUOUS_KEYWORDS
            }
        )
    )
    keyword_overlap = model.keywords.op("&&")(cast(array(product_keywords), ARRAY(Text)))
    print_service = any_ilike(PRINT_SERVICE_TERMS)
    return and_(
        or_(print_service, keyword_overlap),
        ~any_ilike(CIVIL_WORK_TERMS),
        ~any_ilike(NON_PRINT_PRODUCT_TERMS),
    )
