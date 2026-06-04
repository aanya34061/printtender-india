import re


def parse_value(value: object) -> float:
    text = str(value or "").strip()
    if not text:
        return 0.0

    normalized = (
        text.replace("₹", "")
        .replace("Rs.", "")
        .replace("Rs", "")
        .replace("INR", "")
        .replace(",", "")
        .strip()
    )
    normalized = re.sub(r"(?<=\d)(?=[A-Za-z])", " ", normalized)
    parts = normalized.split()
    try:
        amount = float(parts[0])
    except (IndexError, ValueError):
        return 0.0

    unit = " ".join(parts[1:]).casefold()
    if unit in {"l", "lk", "lks"} or "lakh" in unit or "lac" in unit:
        return amount * 100000
    if unit in {"c", "cr"} or "crore" in unit:
        return amount * 10000000
    if unit in {"k"} or "thousand" in unit:
        return amount * 1000
    return amount


VALUE_IN_TEXT_RE = re.compile(
    r"(?:₹|Rs\.?|INR)\s*([0-9][0-9,]*(?:\.\d+)?)\s*(Crores?|Cr|Lakh|Lakhs|Lac|Lacs|L|Thousand|K)?\b",
    flags=re.IGNORECASE,
)


def extract_value_text(*parts: object) -> str | None:
    text = " ".join(str(part or "") for part in parts if part)
    for match in VALUE_IN_TEXT_RE.finditer(text):
        amount, unit = match.groups()
        parsed = parse_value(f"{amount} {unit or ''}")
        if parsed >= 1000:
            return match.group(0)
    return None
