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
    "MP Tenders",
    "eproc.mp.gov.in",
    "CPPP",
    "GeM",
    "PNB Tenders",
    "Canara Bank Tenders",
    "Central Bank of India Tenders",
    "Bank of India Tenders",
    "Indian Bank Tenders",
    "UCO Bank Tenders",
    "Indian Overseas Bank Tenders",
    "LIC Tenders",
    "MP PWD",
    "MPBSE",
    "MP Forest",
    "MP Info",
    "State-MP",
    "State-UP",
    "State-MH",
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

LIVE_PORTAL_SOURCES: tuple[str, ...] = PORTAL_SOURCES

ACTIVE_TENDER_SOURCES: tuple[str, ...] = PORTAL_SOURCES
ACTIVE_FETCH_SOURCES: tuple[str, ...] = (
    *PORTAL_SOURCES,
    *NEWSPAPER_SOURCES,
    "Epaper OCR",
)

SOURCE_DISPLAY_ALIASES: dict[str, str] = {
    "GeM": "gem.gov.in",
    "State-MH": "Maharashtra Tenders",
}


def display_source(source: str | None, portal_url: str | None = None) -> str | None:
    if source == "CPPP":
        return "CPPP"
    return canonicalize_source(source)


def is_active_source(source: str | None) -> bool:
    return source in ACTIVE_TENDER_SOURCES


def canonicalize_source(source: str | None) -> str | None:
    if source is None:
        return None
    return SOURCE_DISPLAY_ALIASES.get(source, source)


def expand_source_filter(source: str | None) -> tuple[str, ...]:
    if not source:
        return ()
    if source == "etenders.gov.in":
        return ("CPPP",)
    if source == "gem.gov.in":
        return ("GeM",)
    if source == "Maharashtra Tenders":
        return ("Maharashtra Tenders", "State-MH")
    return (source,)
