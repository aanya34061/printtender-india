from __future__ import annotations

import random
import re
from typing import List
from urllib.parse import urljoin, urlparse

try:
    import httpx
    _HTTPX_AVAILABLE = True
except Exception:
    httpx = None
    _HTTPX_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    _BS4_AVAILABLE = True
except Exception:
    BeautifulSoup = None
    _BS4_AVAILABLE = False

from app.fetchers.base import BaseFetcher
import time

# Minimal newspaper scrapers. Each function accepts keyword and returns list[dict].
# They are intentionally conservative: parse public tender/classified listing pages
# and extract anchor-based items containing tender-related keywords.

USER_AGENTS = [
    # Three Chrome-like UA strings to rotate
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.5790.170 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.96 Safari/537.36",
]

# Keywords (English + Hindi) to detect tender notices in free-form text
NOTICE_KEYWORDS = ("tender", "tenders", "tender notice", "निविदा", "NIT", "sealed tender", "quotation", "rate contract")


def _fetch_html(url: str) -> str:
    headers = {"User-Agent": random.choice(USER_AGENTS)}
    # Conservative delay between requests (avoid instantiating abstract BaseFetcher)
    time.sleep(random.uniform(2, 4))
    if not _HTTPX_AVAILABLE:
        print("newspapers: httpx not installed; skipping network fetch")
        return ""
    with httpx.Client(timeout=20, follow_redirects=True, headers=headers) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text


def _find_candidate_anchors(html: str, base_url: str) -> List[tuple[str, str, str]]:
    """Return list of (title, href, context_text) for anchors likely to be tender notices."""
    if not _BS4_AVAILABLE or not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    anchors = []
    for a in soup.find_all("a", href=True):
        text = (a.get_text(" ", strip=True) or "").strip()
        if not text:
            continue
        context = " ".join((a.find_parent("div") or a).get_text(" ", strip=True).split())
        combined = f"{text} {context}".casefold()
        if any(k.casefold() in combined for k in NOTICE_KEYWORDS):
            href = urljoin(base_url, a["href"])
            anchors.append((text, href, context))
    return anchors


class _NewspaperWorker(BaseFetcher):
    def fetch(self, keyword: str) -> list[dict]:
        # satisfy abstract base class — this worker is used for record construction only
        return []

    def build(self, *, title: str, portal_source: str, portal_url: str, context: str, keyword_hit: str) -> dict:
        rec = self.build_record(
            ref_number=None,
            title=title,
            organisation=None,
            state=None,
            portal_source=portal_source,
            deadline_raw=None,
            value_raw=None,
            portal_url=portal_url,
            keyword_hit=keyword_hit,
            tender_id=None,
            link_verified=False,
        )
        # Ensure newspapers are marked explicitly
        rec["link_type"] = "newspaper"
        return rec


# Text-based newspaper scrapers (conservative implementations)

def scrape_toi(keyword: str) -> list[dict]:
    try:
        urls = ["https://timesofindia.indiatimes.com/tenders"]
        worker = _NewspaperWorker()
        tenders = []
        for url in urls:
            try:
                html = _fetch_html(url)
            except Exception:
                continue
            for title, href, context in _find_candidate_anchors(html, url):
                tenders.append(worker.build(title=title, portal_source="TOI Tenders", portal_url=href, context=context, keyword_hit=keyword))
        return tenders
    except Exception as exc:
        print(f"scrape_toi error: {exc}")
        return []


def scrape_ht(keyword: str) -> list[dict]:
    try:
        urls = ["https://hindustantimes.com/classifieds/tenders"]
        worker = _NewspaperWorker()
        tenders = []
        for url in urls:
            try:
                html = _fetch_html(url)
            except Exception:
                continue
            for title, href, context in _find_candidate_anchors(html, url):
                tenders.append(worker.build(title=title, portal_source="HT Tenders", portal_url=href, context=context, keyword_hit=keyword))
        return tenders
    except Exception as exc:
        print(f"scrape_ht error: {exc}")
        return []


def scrape_et(keyword: str) -> list[dict]:
    try:
        urls = ["https://economictimes.indiatimes.com/tenders"]
        worker = _NewspaperWorker()
        tenders = []
        for url in urls:
            try:
                html = _fetch_html(url)
            except Exception:
                continue
            for title, href, context in _find_candidate_anchors(html, url):
                tenders.append(worker.build(title=title, portal_source="ET Tenders", portal_url=href, context=context, keyword_hit=keyword))
        return tenders
    except Exception as exc:
        print(f"scrape_et error: {exc}")
        return []


def scrape_thehindu(keyword: str) -> list[dict]:
    try:
        urls = ["https://thehindu.com/classifieds/tenders"]
        worker = _NewspaperWorker()
        tenders = []
        for url in urls:
            try:
                html = _fetch_html(url)
            except Exception:
                continue
            for title, href, context in _find_candidate_anchors(html, url):
                tenders.append(worker.build(title=title, portal_source="The Hindu Tenders", portal_url=href, context=context, keyword_hit=keyword))
        return tenders
    except Exception as exc:
        print(f"scrape_thehindu error: {exc}")
        return []


# MP-focused newspapers

def scrape_bhaskar(keyword: str) -> list[dict]:
    try:
        urls = ["https://www.bhaskar.com/tenders", "https://www.bhaskar.com/local/" ]
        worker = _NewspaperWorker()
        tenders = []
        for url in urls:
            try:
                html = _fetch_html(url)
            except Exception:
                continue
            for title, href, context in _find_candidate_anchors(html, url):
                tenders.append(worker.build(title=title, portal_source="Dainik Bhaskar", portal_url=href, context=context, keyword_hit=keyword))
        return tenders
    except Exception as exc:
        print(f"scrape_bhaskar error: {exc}")
        return []


def scrape_patrika(keyword: str) -> list[dict]:
    try:
        urls = ["https://www.patrika.com/tenders", "https://www.patrika.com/epaper/"]
        worker = _NewspaperWorker()
        tenders = []
        for url in urls:
            try:
                html = _fetch_html(url)
            except Exception:
                continue
            for title, href, context in _find_candidate_anchors(html, url):
                tenders.append(worker.build(title=title, portal_source="Patrika", portal_url=href, context=context, keyword_hit=keyword))
        return tenders
    except Exception as exc:
        print(f"scrape_patrika error: {exc}")
        return []


def scrape_naidunia(keyword: str) -> list[dict]:
    try:
        urls = ["https://www.naidunia.com/tenders", "https://naidunia.com/epaper"]
        worker = _NewspaperWorker()
        tenders = []
        for url in urls:
            try:
                html = _fetch_html(url)
            except Exception:
                continue
            for title, href, context in _find_candidate_anchors(html, url):
                tenders.append(worker.build(title=title, portal_source="Nai Dunia", portal_url=href, context=context, keyword_hit=keyword))
        return tenders
    except Exception as exc:
        print(f"scrape_naidunia error: {exc}")
        return []


def scrape_navbharat(keyword: str) -> list[dict]:
    try:
        urls = ["https://navbharattimes.indiatimes.com/tenders"]
        worker = _NewspaperWorker()
        tenders = []
        for url in urls:
            try:
                html = _fetch_html(url)
            except Exception:
                continue
            for title, href, context in _find_candidate_anchors(html, url):
                tenders.append(worker.build(title=title, portal_source="Navbharat", portal_url=href, context=context, keyword_hit=keyword))
        return tenders
    except Exception as exc:
        print(f"scrape_navbharat error: {exc}")
        return []


def scrape_jagran(keyword: str) -> list[dict]:
    try:
        urls = ["https://www.jagran.com/tenders"]
        worker = _NewspaperWorker()
        tenders = []
        for url in urls:
            try:
                html = _fetch_html(url)
            except Exception:
                continue
            for title, href, context in _find_candidate_anchors(html, url):
                tenders.append(worker.build(title=title, portal_source="Dainik Jagran", portal_url=href, context=context, keyword_hit=keyword))
        return tenders
    except Exception as exc:
        print(f"scrape_jagran error: {exc}")
        return []


def scrape_amarujala(keyword: str) -> list[dict]:
    try:
        urls = ["https://www.amarujala.com/tenders"]
        worker = _NewspaperWorker()
        tenders = []
        for url in urls:
            try:
                html = _fetch_html(url)
            except Exception:
                continue
            for title, href, context in _find_candidate_anchors(html, url):
                tenders.append(worker.build(title=title, portal_source="Amar Ujala", portal_url=href, context=context, keyword_hit=keyword))
        return tenders
    except Exception as exc:
        print(f"scrape_amarujala error: {exc}")
        return []


# Notice aggregators

def scrape_tendernotice(keyword: str) -> list[dict]:
    try:
        urls = ["https://tendernotice.co.in"]
        worker = _NewspaperWorker()
        tenders = []
        for url in urls:
            try:
                html = _fetch_html(url)
            except Exception:
                continue
            for title, href, context in _find_candidate_anchors(html, url):
                tenders.append(worker.build(title=title, portal_source="Tender Notice India", portal_url=href, context=context, keyword_hit=keyword))
        return tenders
    except Exception as exc:
        print(f"scrape_tendernotice error: {exc}")
        return []


def scrape_indiatendernotice(keyword: str) -> list[dict]:
    try:
        urls = ["https://indiatendernotice.com"]
        worker = _NewspaperWorker()
        tenders = []
        for url in urls:
            try:
                html = _fetch_html(url)
            except Exception:
                continue
            for title, href, context in _find_candidate_anchors(html, url):
                tenders.append(worker.build(title=title, portal_source="India Tender Notice", portal_url=href, context=context, keyword_hit=keyword))
        return tenders
    except Exception as exc:
        print(f"scrape_indiatendernotice error: {exc}")
        return []


def scrape_publicnotice(keyword: str) -> list[dict]:
    try:
        urls = ["https://publicnotice.co.in"]
        worker = _NewspaperWorker()
        tenders = []
        for url in urls:
            try:
                html = _fetch_html(url)
            except Exception:
                continue
            for title, href, context in _find_candidate_anchors(html, url):
                tenders.append(worker.build(title=title, portal_source="Public Notice India", portal_url=href, context=context, keyword_hit=keyword))
        return tenders
    except Exception as exc:
        print(f"scrape_publicnotice error: {exc}")
        return []


__all__ = [
    "scrape_toi",
    "scrape_ht",
    "scrape_et",
    "scrape_thehindu",
    "scrape_bhaskar",
    "scrape_patrika",
    "scrape_naidunia",
    "scrape_navbharat",
    "scrape_jagran",
    "scrape_amarujala",
    "scrape_tendernotice",
    "scrape_indiatendernotice",
    "scrape_publicnotice",
]
