from app.fetchers.deeplinks import (
    GENERIC_HOMEPAGE_URLS,
    build_deep_link,
    classify_link,
    extract_nic_tender_id,
    is_document_download_link,
    is_brittle_nic_direct_link,
    is_generic_homepage_url,
    is_generic_link,
    resolve_link,
)


# ── build_deep_link ────────────────────────────────────────────────────────


def test_cppp_with_tender_id_uses_direct_link():
    link = build_deep_link("CPPP", "CPPP/2025/04/123", "S12345678")
    assert "eprocure.gov.in" in link
    assert "sp=S12345678" in link
    assert "FrontEndTendersByNIT" in link


def test_cppp_without_tender_id_uses_portal_keyword_search():
    link = build_deep_link("CPPP", "CPPP/2025/04/123", None)
    assert "eprocure.gov.in" in link
    assert "FrontEndTendersByKeyword" in link
    assert "keyword=CPPP%2F2025%2F04%2F123" in link
    assert link not in GENERIC_HOMEPAGE_URLS


def test_fallback_is_not_homepage():
    link = build_deep_link("CPPP", "REF-ABC-123", None)
    assert link != "https://eprocure.gov.in"
    assert link not in GENERIC_HOMEPAGE_URLS


def test_gem_with_captured_card_href_uses_actual_href():
    link = build_deep_link("GeM", "GEM/2025/B/12345", "/showbidDocument/123456")
    assert link == "https://bidplus.gem.gov.in/showbidDocument/123456"


def test_gem_with_captured_document_id_uses_showbid_document():
    link = build_deep_link("GeM", "GEM/2025/B/12345", "123456")
    assert link == "https://bidplus.gem.gov.in/showbidDocument/123456"


def test_gem_with_tender_id_does_not_construct_bid_details():
    link = build_deep_link("GeM", "GEM/2025/B/12345", "GEM-2025-B-12345")
    assert link == "https://bidplus.gem.gov.in/all-bids?search_bid=GEM%2F2025%2FB%2F12345"
    assert "bid-details" not in link


def test_gem_ref_without_tender_id_falls_back_to_all_bids():
    link = build_deep_link("GeM", "GEM/2025/B/99", None)
    assert link == "https://bidplus.gem.gov.in/all-bids?search_bid=GEM%2F2025%2FB%2F99"


def test_gem_without_ref_falls_back_to_all_bids():
    link = build_deep_link("GeM", "", None)
    assert link == "https://bidplus.gem.gov.in/all-bids"


def test_gem_showbid_document_is_marked_as_download_link():
    assert is_document_download_link(
        "https://bidplus.gem.gov.in/showbidDocument/9217773"
    )


def test_gem_resolve_link_preserves_captured_direct_url():
    url, link_type = resolve_link(
        "GeM",
        "GEM/2026/B/7439701",
        None,
        "https://bidplus.gem.gov.in/showbidDocument/9217773",
        True,
    )

    assert url == "https://bidplus.gem.gov.in/showbidDocument/9217773"
    assert link_type == "direct"


def test_state_mp_with_tender_id():
    link = build_deep_link("State-MP", "MP/2025/01", "S98765432")
    assert "mptenders.gov.in" in link
    assert "FrontEndTendersByKeyword" in link
    assert "keyword=MP%2F2025%2F01" in link


def test_state_mh_with_tender_id_uses_portal_search():
    link = build_deep_link("State-MH", "MH/2025/01", "S98765432")
    assert "mahatenders.gov.in" in link
    assert "FrontEndTendersByKeyword" in link
    assert "keyword=MH%2F2025%2F01" in link


def test_state_rj_without_tender_id_uses_portal_search():
    link = build_deep_link("State-RJ", "RJ/2025/001", None)
    assert "sppp.rajasthan.gov.in" in link
    assert "FrontEndTendersByKeyword" in link


def test_unknown_portal_returns_google_search():
    link = build_deep_link("UnknownPortal", "XYZ-001", None)
    assert "google.com/search" in link
    assert "XYZ-001" in link


# ── extract_nic_tender_id ──────────────────────────────────────────────────


def test_extract_nic_tender_id_with_sp_param():
    url = "https://eprocure.gov.in/eprocure/app?component=%24DirectLink&page=FrontEndTendersByNIT&service=direct&session=T&sp=S12345678"
    assert extract_nic_tender_id(url) == "S12345678"


def test_extract_nic_tender_id_short_ref():
    url = "https://mptenders.gov.in/nicgep/app?page=FrontEndViewTender&sp=MP-PRINT-001"
    assert extract_nic_tender_id(url) == "MP-PRINT-001"


def test_extract_nic_tender_id_missing():
    assert extract_nic_tender_id("https://eprocure.gov.in") is None
    assert extract_nic_tender_id("") is None


# ── classify_link ──────────────────────────────────────────────────────────


def test_classify_link_empty_is_search():
    assert classify_link("", False) == "search"


def test_classify_link_homepage_is_search():
    assert classify_link("https://eprocure.gov.in", False) == "search"
    assert classify_link("https://eprocure.gov.in/", False) == "search"
    assert classify_link("https://etenders.gov.in", False) == "search"
    assert classify_link("https://etenders.gov.in/eprocure/app", False) == "search"
    assert classify_link("https://bidplus.gem.gov.in/all-bids", False) == "search"


def test_is_generic_homepage_url_normalises_trailing_slash():
    assert is_generic_homepage_url("https://mptenders.gov.in/nicgep/app/")


def test_is_generic_link_identifies_homepage_and_direct_sp():
    assert is_generic_link("https://mptenders.gov.in/nicgep/app")
    assert not is_generic_link(
        "https://mptenders.gov.in/nicgep/app?component=%24DirectLink&page=FrontEndTendersByNIT&service=direct&session=T&sp=S98765432"
    )


def test_nic_link_without_sp_s_is_generic_even_with_directlink_page():
    assert is_generic_link(
        "https://mptenders.gov.in/nicgep/app?component=%24DirectLink&page=FrontEndTendersByNIT&service=direct"
    )


def test_brittle_nic_advanced_search_link_is_detected():
    assert is_brittle_nic_direct_link(
        "https://mahatenders.gov.in/nicgep/app?component=%24DirectLink_0&page=FrontEndAdvancedSearchResult&service=direct&session=T&sp=SWp8FvorQMqWExhnmC"
    )


def test_nic_keyword_search_is_search_fallback():
    link = "https://mptenders.gov.in/nicgep/app?page=FrontEndTendersByKeyword&service=page&keyword=MP-PRINT-001"
    assert is_generic_link(link)
    assert classify_link(link, False) == "search"


def test_tenderdekho_without_slug_uses_site_search():
    link = build_deep_link("TenderDekho", "TD-REF-001", None)
    assert link == "https://tenderdekho.com/tenders?search=TD-REF-001"


def test_tenderdekho_with_slug_uses_tender_path():
    link = build_deep_link("TenderDekho", "TD-REF-001", "some-tender-slug")
    assert link == "https://tenderdekho.com/tender/some-tender-slug"


def test_classify_link_google_is_search():
    assert (
        classify_link("https://www.google.com/search?q=REF123+tender", False)
        == "search"
    )


def test_classify_link_verified_is_direct():
    link = "https://eprocure.gov.in/eprocure/app?sp=S12345678"
    assert classify_link(link, True) == "direct"


def test_classify_link_etenders_direct_sp_is_direct_when_verified():
    link = "https://etenders.gov.in/eprocure/app?component=%24DirectLink&page=FrontEndTendersByNIT&service=direct&session=T&sp=S12345678"
    assert classify_link(link, True) == "direct"


def test_classify_link_unverified_non_homepage_is_deep():
    link = "https://eprocure.gov.in/eprocure/app?component=%24DirectLink&page=FrontEndTendersByNIT&service=direct&session=T&sp=S12345678"
    assert classify_link(link, False) == "deep"


def test_classify_link_bid_details_unverified_is_deep():
    link = "https://bidplus.gem.gov.in/bidding/bid-details/BID-2025-B-12345"
    assert classify_link(link, False) == "deep"


# ── GENERIC_HOMEPAGE_URLS completeness ────────────────────────────────────


def test_generic_homepage_urls_covers_all_portals():
    required = [
        "https://eprocure.gov.in",
        "https://etenders.gov.in",
        "https://bidplus.gem.gov.in",
        "https://mptenders.gov.in",
        "https://etender.up.nic.in",
        "https://mahatenders.gov.in",
        "https://sppp.rajasthan.gov.in",
        "",
    ]
    for url in required:
        assert (
            url in GENERIC_HOMEPAGE_URLS
        ), f"{url!r} missing from GENERIC_HOMEPAGE_URLS"
