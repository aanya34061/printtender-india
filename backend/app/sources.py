NEWSPAPER_SOURCES: tuple[str, ...] = (
    "TOI Tenders",
    "HT Tenders",
    "ET Tenders",
    "The Hindu Tenders",
    "Dainik Bhaskar",
    "Patrika",
    "Nai Dunia",
    "Nav Bharat",
    "Dainik Jagran",
    "Amar Ujala",
    "Deshbandhu",
    "Raj Express",
    "Peoples Samachar",
    "Dabang Dunia",
    "Free Press Journal",
    "Pradesh Today",
    "Agniban",
    "Nav Swadesh",
    "Swadesh",
    "Hari Bhoomi",
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

SOURCE_DISPLAY_ALIASES: dict[str, str] = {
    "GeM": "gem.gov.in",
    "State-MH": "Maharashtra Tenders",
    "Naidunia": "Nai Dunia",
    "Rajasthan Patrika": "Patrika",
    "Navbharat": "Nav Bharat",
}

ALL_KNOWN_SOURCES: set[str] = (
    set(PORTAL_SOURCES)
    | set(NEWSPAPER_SOURCES)
    | set(SOURCE_DISPLAY_ALIASES.keys())
    | set(SOURCE_DISPLAY_ALIASES.values())
)

ACTIVE_TENDER_SOURCES: tuple[str, ...] = tuple(sorted(ALL_KNOWN_SOURCES))
ACTIVE_FETCH_SOURCES: tuple[str, ...] = (
    *ACTIVE_TENDER_SOURCES,
    "Epaper OCR",
)


def display_source(source: str | None, portal_url: str | None = None) -> str | None:
    if source == "CPPP":
        return "CPPP"
    return canonicalize_source(source)


def is_active_source(source: str | None) -> bool:
    return (
        source in ACTIVE_TENDER_SOURCES
        or canonicalize_source(source) in ACTIVE_TENDER_SOURCES
    )


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
    if source in ("Nai Dunia", "Naidunia"):
        return ("Nai Dunia", "Naidunia")
    if source in ("Patrika", "Rajasthan Patrika"):
        return ("Patrika", "Rajasthan Patrika")
    if source in ("Nav Bharat", "Navbharat"):
        return ("Nav Bharat", "Navbharat")
    return (source,)
