NEWSPAPER_SOURCES: tuple[str, ...] = (
    "TOI Tenders",
    "HT Tenders",
    "ET Tenders",
    "The Hindu Tenders",
    "Dainik Bhaskar",
    "Patrika",
    "Nai Dunia",
    "Navbharat",
    "Dainik Jagran",
    "Amar Ujala",
    "Tender Notice India",
    "India Tender Notice",
    "Public Notice India",
)

GOVERNMENT_PORTAL_SOURCES: tuple[str, ...] = (
    "CPPP",
    "GeM",
    "MP Tenders",
    "MP PWD",
    "MPBSE",
    "MP Forest",
    "MP Info",
    "State-MP",
    "State-UP",
    "State-MH",
    "Maharashtra Tenders",
    "State-RJ",
)

AGGREGATOR_SOURCES: tuple[str, ...] = (
    "TenderDekho",
    "BidAssist",
)

PORTAL_SOURCES: tuple[str, ...] = (
    *GOVERNMENT_PORTAL_SOURCES,
    *AGGREGATOR_SOURCES,
)

ACTIVE_TENDER_SOURCES: tuple[str, ...] = (*NEWSPAPER_SOURCES, *PORTAL_SOURCES)
ACTIVE_FETCH_SOURCES: tuple[str, ...] = (*ACTIVE_TENDER_SOURCES, "Epaper OCR")

SOURCE_DISPLAY_ALIASES: dict[str, str] = {
    "State-MH": "Maharashtra Tenders",
}


def is_active_source(source: str | None) -> bool:
    return source in ACTIVE_TENDER_SOURCES


def canonicalize_source(source: str | None) -> str | None:
    if source is None:
        return None
    return SOURCE_DISPLAY_ALIASES.get(source, source)


def expand_source_filter(source: str | None) -> tuple[str, ...]:
    if not source:
        return ()
    if source == "Maharashtra Tenders":
        return ("Maharashtra Tenders", "State-MH")
    return (source,)
