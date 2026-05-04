from app.fetchers.deeplinks import (
    GENERIC_HOMEPAGE_URLS,
    build_deep_link,
    classify_link,
    extract_nic_tender_id,
    is_generic_homepage_url,
    is_generic_link,
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


def test_gem_with_ref_uses_search_url():
    link = build_deep_link("GeM", "GEM/2025/B/12345", "GEM-2025-B-12345")
    assert "bidplus.gem.gov.in" in link
    assert "bid-details" in link
    assert "GEM" in link


def test_gem_search_url_encodes_ref():
    link = build_deep_link("GeM", "GEM/2025/B/99", None)
    assert "bidplus.gem.gov.in" in link
    assert "search_bid" in link


def test_gem_without_ref_falls_back_to_all_bids():
    link = build_deep_link("GeM", "", None)
    assert link == "https://bidplus.gem.gov.in/all-bids?search_bid="


def test_state_mp_with_tender_id():
    link = build_deep_link("State-MP", "MP/2025/01", "S98765432")
    assert "mptenders.gov.in" in link
    assert "sp=S98765432" in link
    assert "FrontEndTendersByNIT" in link


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
    assert classify_link("https://bidplus.gem.gov.in/all-bids", False) == "search"


def test_is_generic_homepage_url_normalises_trailing_slash():
    assert is_generic_homepage_url("https://mptenders.gov.in/nicgep/app/")


def test_is_generic_link_identifies_homepage_and_direct_sp():
    assert is_generic_link("https://mptenders.gov.in/nicgep/app")
    assert not is_generic_link(
        "https://mptenders.gov.in/nicgep/app?component=%24DirectLink&page=FrontEndTendersByNIT&service=direct&session=T&sp=S98765432"
    )


def test_classify_link_google_is_search():
    assert (
        classify_link("https://www.google.com/search?q=REF123+tender", False)
        == "search"
    )


def test_classify_link_verified_is_direct():
    link = "https://eprocure.gov.in/eprocure/app?sp=S12345678"
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
