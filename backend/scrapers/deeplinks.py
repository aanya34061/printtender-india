from app.fetchers.deeplinks import (
    GENERIC_HOMEPAGE_URLS,
    build_deep_link,
    classify_link,
    extract_nic_tender_id,
    has_nic_direct_sp,
    is_generic_homepage_url,
    is_generic_link,
    resolve_link,
)

__all__ = [
    "GENERIC_HOMEPAGE_URLS",
    "build_deep_link",
    "classify_link",
    "extract_nic_tender_id",
    "has_nic_direct_sp",
    "is_generic_homepage_url",
    "is_generic_link",
    "resolve_link",
]
