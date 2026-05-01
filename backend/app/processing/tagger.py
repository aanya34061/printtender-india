from app.fetchers.base import PRINTING_KEYWORDS


def tag_printing_keywords(text: str) -> list[str]:
    normalized = text.casefold()
    return [keyword for keyword in PRINTING_KEYWORDS if keyword.casefold() in normalized]
