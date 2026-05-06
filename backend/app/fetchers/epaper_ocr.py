from __future__ import annotations

import os
from datetime import datetime
from typing import List

# Optional OCR module. Import heavy deps only if available — otherwise remain no-op.

def _safe_import_tesseract():
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
        return pytesseract, Image
    except Exception:
        return None, None


def scrape_epapers_for_mp(keyword: str) -> List[dict]:
    """OCR-based scraping for MP editions (optional). Returns empty list if dependencies missing.

    This function is intentionally conservative: it only runs when pytesseract is
    installed and will return an empty list without raising if not present.
    """
    pytesseract, Image = _safe_import_tesseract()
    if not pytesseract:
        print("epaper_ocr: pytesseract not available — skipping OCR sources")
        return []

    # Placeholder implementation: real epaper workflows require site-specific fetching
    # and are intentionally left minimal here to avoid heavy changes. The function
    # demonstrates the optional import pattern and returns [] when nothing found.
    print("epaper_ocr: pytesseract present — but no epaper handlers implemented yet")
    return []


__all__ = ["scrape_epapers_for_mp"]
