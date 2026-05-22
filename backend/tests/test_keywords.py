from app.keywords import IMAGE_PRODUCT_KEYWORDS, PRINT_KEYWORDS


def test_image_product_keywords_cover_supplied_product_list() -> None:
    expected = {
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
    }

    assert expected.issubset(set(IMAGE_PRODUCT_KEYWORDS))
    assert expected.issubset(set(PRINT_KEYWORDS))


def test_exact_user_spellings_are_covered_during_fetch() -> None:
    expected = {
        "calenders",
        "brouchers",
        "catalogus",
        "annual report",
        "stationary",
    }

    assert expected.issubset(set(IMAGE_PRODUCT_KEYWORDS))
    assert expected.issubset(set(PRINT_KEYWORDS))
