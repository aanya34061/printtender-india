"""
Central keyword lists for PrintTender India.
Used by all fetchers and the Celery scheduler.
"""

def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        output.append(value)
    return output


PRODUCT_KEYWORD_CANONICAL: list[str] = [
    "calendars",
    "diary",
    "sticker",
    "registers",
    "books",
    "forms",
    "papers",
    "note books",
    "brochures",
    "flyers",
    "visiting cards",
    "certificates",
    "receipt books",
    "prospectus",
    "catalogues",
    "pass books",
    "duplex box",
    "cards",
    "answer books",
    "exercise books",
    "tags",
    "posters",
    "banners",
    "labels",
    "desk pads",
    "envelopes",
    "marks sheet",
    "stationary",
    "stationery",
    "note sheets",
    "files",
    "pamphlets",
    "annual reports",
    "souvenir",
]

PRODUCT_KEYWORD_VARIANTS: dict[str, tuple[str, ...]] = {
    "calendars": ("calendar", "calender", "calenders"),
    "books": ("book",),
    "forms": ("form",),
    "papers": ("paper",),
    "note books": ("notebook", "notebook"),
    "brochures": ("brochure", "broucher", "brouchers"),
    "flyers": ("flyer",),
    "visiting cards": ("visiting card",),
    "certificates": ("certificate",),
    "receipt books": ("receipt book",),
    "catalogues": ("catalogue", "catalog", "catalogs", "catalogus"),
    "pass books": ("pass book",),
    "cards": ("card",),
    "answer books": ("answer book",),
    "exercise books": ("exercise book",),
    "tags": ("tag",),
    "posters": ("poster",),
    "banners": ("banner",),
    "labels": ("label",),
    "desk pads": ("desk pad",),
    "envelopes": ("envelope",),
    "files": ("file",),
    "pamphlets": ("pamphlet",),
    "annual reports": ("annual report",),
    "souvenir": ("souvenirs",),
}

IMAGE_PRODUCT_KEYWORDS: list[str] = _dedupe(
    [
        *PRODUCT_KEYWORD_CANONICAL,
        *[
            variant
            for variants in PRODUCT_KEYWORD_VARIANTS.values()
            for variant in variants
        ],
    ]
)

PRINT_KEYWORDS: list[str] = [
    # ── Owner's product list from supplied image ───────────────────────
    *IMAGE_PRODUCT_KEYWORDS,
    # ── Hindi transliterations (for CPPP / state portal searches) ───────
    "पंचांग",
    "डायरी",
    "स्टिकर",
    "रजिस्टर",
    "पुस्तक",
    "प्रपत्र",
    "कागज",
    "नोटबुक",
    "ब्रोशर",
    "पर्चा",
    "विजिटिंग कार्ड",
    "प्रमाण पत्र",
    "रसीद बुक",
    "विवरणिका",
    "सूची पत्र",
    "पासबुक",
    "कार्ड",
    "उत्तर पुस्तिका",
    "अभ्यास पुस्तिका",
    "टैग",
    "पोस्टर",
    "बैनर",
    "लेबल",
    "लिफाफा",
    "अंक तालिका",
    "स्टेशनरी",
    "फाइल",
    "वार्षिक प्रतिवेदन",
    "स्मारिका",
    # ── Common government tender search terms ───────────────────────────
    "offset printing",
    "digital printing",
    "security printing",
    "government forms printing",
    "textbook printing",
    "gazette printing",
    "ballot paper",
    "toner cartridge",
    "packaging printing",
    "label printing",
    "flex printing",
    "screen printing",
    "letterpress",
    "book binding",
    "lamination",
]

# Alias kept for backwards compatibility
PRODUCT_KEYWORDS = IMAGE_PRODUCT_KEYWORDS
PRINTING_KEYWORDS = PRINT_KEYWORDS
