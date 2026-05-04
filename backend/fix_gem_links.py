from __future__ import annotations

import asyncio
import random
import re
from dataclasses import dataclass
from urllib.parse import urljoin

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright
from sqlalchemy import select, update

from app.database import async_session, run_startup_migrations
from app.fetchers.base import USER_AGENT
from app.fetchers.deeplinks import classify_link
from app.models import Tender


GEM_BASE_URL = "https://bidplus.gem.gov.in"
GEM_ALL_BIDS_URL = f"{GEM_BASE_URL}/all-bids"
GEM_SEARCH_STATUSES = ("ongoing_bids", "bidrastatus")
BAD_GEM_BID_DETAILS_RE = re.compile(
    r"/bid-details/((?:GEM|BID)-\d{4}-B-\d+)\b",
    flags=re.IGNORECASE,
)
GEM_BID_RE = re.compile(r"\bGEM/\d{4}/B/\d+\b", flags=re.IGNORECASE)
GEM_HYPHEN_BID_RE = re.compile(r"\bGEM-\d{4}-B-\d+\b", flags=re.IGNORECASE)
GEM_DOCUMENT_RE = re.compile(r"showbidDocument/([^?#]+)", flags=re.IGNORECASE)


@dataclass(frozen=True)
class BadGemLink:
    id: int
    ref_number: str
    tender_id: str | None
    portal_url: str


async def backfill_bad_gem_links() -> int:
    await run_startup_migrations()
    candidates = await _load_bad_gem_links()
    if not candidates:
        print("fix_gem_links scanned=0 updated=0")
        return 0

    updates: dict[int, tuple[str, bool]] = {}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(
            headless=False,
            args=["--headless=new", "--ignore-certificate-errors"],
        )
        try:
            context = await browser.new_context(user_agent=USER_AGENT)
            page = await context.new_page()
            for candidate in candidates:
                bid_number = _bid_number_for_search(candidate)
                if not bid_number:
                    print(f"fix_gem_links skipped id={candidate.id} reason=no_bid_number")
                    continue
                real_url = await _lookup_bid_url(page, bid_number)
                if real_url:
                    updates[candidate.id] = (real_url, True)
                    print(
                        "fix_gem_links found "
                        f"id={candidate.id} bid={bid_number} url={real_url}"
                    )
                else:
                    updates[candidate.id] = (GEM_ALL_BIDS_URL, False)
                    print(
                        "fix_gem_links fallback "
                        f"id={candidate.id} bid={bid_number} url={GEM_ALL_BIDS_URL}"
                    )
        finally:
            await browser.close()

    updated = await _apply_updates(updates)
    print(f"fix_gem_links scanned={len(candidates)} updated={updated}")
    return updated


async def _load_bad_gem_links() -> list[BadGemLink]:
    async with async_session() as session:
        rows = await session.execute(
            select(Tender.id, Tender.ref_number, Tender.tender_id, Tender.portal_url)
            .where(Tender.portal_source == "GeM")
            .where(Tender.portal_url.ilike("%/bid-details/%"))
        )
        candidates: list[BadGemLink] = []
        for row in rows:
            portal_url = row.portal_url or ""
            if BAD_GEM_BID_DETAILS_RE.search(portal_url):
                candidates.append(
                    BadGemLink(
                        id=row.id,
                        ref_number=row.ref_number,
                        tender_id=row.tender_id,
                        portal_url=portal_url,
                    )
                )
        return candidates


async def _lookup_bid_url(page, bid_number: str) -> str | None:
    await asyncio.sleep(random.uniform(2, 4))
    await page.goto(GEM_ALL_BIDS_URL, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_selector("#searchBid", timeout=30000)
    for status in GEM_SEARCH_STATUSES:
        real_url = await _lookup_bid_url_from_page(page, bid_number, status)
        if real_url:
            return real_url
        real_url = await _lookup_bid_url_from_data(page, bid_number, status)
        if real_url:
            return real_url
    return None


async def _lookup_bid_url_from_page(page, bid_number: str, status: str) -> str | None:
    await page.locator(f"#{status}").check(force=True)
    await page.locator("#searchBid").fill(bid_number)
    await page.locator("#searchBidRA").click()
    card = page.locator(".card").filter(has_text=bid_number).first
    try:
        await card.wait_for(timeout=15000)
    except PlaywrightTimeoutError:
        return None
    return await _bid_href_from_card(card, bid_number)


async def _lookup_bid_url_from_data(page, bid_number: str, status: str) -> str | None:
    document_id = await page.evaluate(
        """async ({bidNumber, status}) => {
            const cname = document.querySelector("#cname")?.value || "csrf_bd_gem_nk";
            const chash = document.querySelector("#chash")?.value || "";
            const payload = {
                param: {searchBid: bidNumber, searchType: "fullText"},
                filter: {
                    bidStatusType: status,
                    byType: "all",
                    highBidValue: "",
                    byEndDate: {from: "", to: ""},
                    sort: "Bid-End-Date-Oldest",
                },
            };
            const body = new URLSearchParams();
            body.set("payload", JSON.stringify(payload));
            body.set(cname, chash);
            const response = await fetch("/all-bids-data", {
                method: "POST",
                headers: {
                    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                    "X-Requested-With": "XMLHttpRequest",
                },
                body,
            });
            if (!response.ok) return null;
            const data = await response.json();
            const docs = data?.response?.response?.docs || [];
            const bid = bidNumber.toUpperCase();
            const doc = docs.find((item) =>
                (item.b_bid_number || []).some((value) => String(value).toUpperCase() === bid)
            );
            if (!doc) return null;
            return String(doc.id || (doc.b_id || [])[0] || "");
        }""",
        {"bidNumber": bid_number, "status": status},
    )
    return (
        f"{GEM_BASE_URL}/showbidDocument/{document_id}"
        if document_id
        else None
    )


async def _bid_href_from_card(card, bid_number: str) -> str | None:
    links = card.locator("a[href]")
    preferred_href: str | None = None
    for index in range(await links.count()):
        link = links.nth(index)
        href = await link.get_attribute("href")
        if not href:
            continue
        text = " ".join((await link.inner_text()).split())
        if bid_number.casefold() == text.casefold():
            return _absolute_gem_url(href)
        if "showbidDocument" in href and preferred_href is None:
            preferred_href = href
    return _absolute_gem_url(preferred_href) if preferred_href else None


async def _apply_updates(updates: dict[int, tuple[str, bool]]) -> int:
    if not updates:
        return 0

    async with async_session() as session:
        updated = 0
        for tender_id, (real_url, verified) in updates.items():
            values = {
                "portal_url": real_url,
                "link_verified": verified,
                "link_type": classify_link(real_url, verified),
            }
            document_id = _document_id_from_url(real_url)
            if document_id:
                values["tender_id"] = document_id
            await session.execute(
                update(Tender)
                .where(Tender.id == tender_id)
                .values(**values)
            )
            updated += 1
        await session.commit()
        return updated


def _bid_number_for_search(candidate: BadGemLink) -> str | None:
    for value in (candidate.ref_number, candidate.tender_id, candidate.portal_url):
        bid_number = _extract_gem_bid_number(value or "")
        if bid_number:
            return bid_number
    return None


def _extract_gem_bid_number(value: str) -> str | None:
    slash_match = GEM_BID_RE.search(value)
    if slash_match:
        return slash_match.group(0).upper()
    hyphen_match = GEM_HYPHEN_BID_RE.search(value)
    if hyphen_match:
        return hyphen_match.group(0).upper().replace("-", "/")
    return None


def _absolute_gem_url(href: str) -> str:
    return href if href.startswith("http") else urljoin(f"{GEM_BASE_URL}/", href)


def _document_id_from_url(url: str) -> str | None:
    match = GEM_DOCUMENT_RE.search(url)
    return match.group(1) if match else None


def main() -> None:
    asyncio.run(backfill_bad_gem_links())


if __name__ == "__main__":
    main()
