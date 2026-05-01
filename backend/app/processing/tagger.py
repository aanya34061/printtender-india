from app.fetchers.base import PRINT_KEYWORDS
from app.processing.deduplicator import deduplicate
from app.processing.normaliser import normalise


CATEGORY_RULES = [
    ("Offset Printing", ("offset", "litho", "letterpress")),
    ("Digital Printing", ("digital print", "laser print", "inkjet", "led print")),
    ("Flexo / Gravure", ("flexo", "gravure", "rotogravure")),
    ("Security Print", ("security", "ballot", "electoral", "cheque", "currency")),
    (
        "Publication",
        ("book", "textbook", "gazette", "annual report", "bulletin", "journal"),
    ),
    ("Packaging", ("packaging", "label", "carton", "box", "wrapper", "pouch")),
    (
        "Stationery",
        ("stationery", "letterhead", "envelope", "visiting card", "diary", "notepad"),
    ),
    ("Consumables", ("toner", "cartridge", "ink", "ribbon", "drum", "fuser")),
    ("Large Format", ("banner", "flex", "hoarding", "vinyl", "signage", "billboard")),
]


def tag_category(title: str) -> str:
    normalized = title.lower()
    for category, keywords in CATEGORY_RULES:
        if any(keyword in normalized for keyword in keywords):
            return category
    return "General Printing"


def pipeline(raw: list[dict]) -> list[dict]:
    df = deduplicate(normalise(raw))
    if df.empty:
        return []
    df["category"] = df["title"].map(tag_category)
    return df.to_dict(orient="records")


def tag_printing_keywords(text: str) -> list[str]:
    normalized = text.casefold()
    return [keyword for keyword in PRINT_KEYWORDS if keyword.casefold() in normalized]
