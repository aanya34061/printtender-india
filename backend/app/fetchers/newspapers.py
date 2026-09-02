from __future__ import annotations

import random
import re
import time
from typing import List
from urllib.parse import urljoin, urlparse, quote_plus

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
from app.keywords import PRINT_KEYWORDS

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.5790.170 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.5845.96 Safari/537.36",
]

# Keywords (English + Hindi) to detect tender notices in free-form text
NOTICE_KEYWORDS = (
    "tender",
    "tenders",
    "tender notice",
    "निविदा",
    "NIT",
    "sealed tender",
    "quotation",
    "rate contract",
    "मुद्रण",
    "छपाई",
    "ई-निविदा",
    "e-tender",
    "chhapayi",
    "prakashan",
    "प्रकाशन",
)


from app.fetchers.base import REQUEST_HEADERS, BaseFetcher


def _fetch_html(url: str) -> str:
    headers = {
        **REQUEST_HEADERS,
        "User-Agent": random.choice(USER_AGENTS),
    }
    time.sleep(random.uniform(0.1, 0.3))
    if not _HTTPX_AVAILABLE:
        print("newspapers: httpx not installed; skipping network fetch")
        return ""
    with httpx.Client(timeout=15, follow_redirects=True, headers=headers) as client:
        r = client.get(url)
        r.raise_for_status()
        return r.text


GENERIC_PATHS = {"", "/", "/home", "/tenders", "/news", "/contact", "/about", "/login", "/search", "/videos", "/sports", "/local", "/pricing", "/blog"}
DISALLOWED_PREFIXES = ("/offering", "/pricing", "/gem-services", "/services", "/news/", "/blog/", "/browse", "/plans", "/categories", "/states", "/cities", "/authorities", "/epaper", "/epaper/")
GENERIC_BOILERPLATE_STARTS = (
    "indian tenders",
    "tender results",
    "all tenders",
    "home",
    "about us",
    "contact us",
    "privacy policy",
    "terms of use",
    "disclaimer",
    "sitemap",
    "feedback",
    "copyright",
    "login",
    "type to search",
    "search price",
    "view all",
)


def _is_valid_newspaper_tender_link(href: str, base_url: str) -> bool:
    full = urljoin(base_url, href)
    parsed = urlparse(full)
    path = parsed.path.rstrip("/").casefold()
    if path in GENERIC_PATHS:
        return False
    if any(path.startswith(p) for p in DISALLOWED_PREFIXES):
        return False
    if "tenderdekho.com" in parsed.netloc:
        return path.startswith(("tender/", "tender-detail/", "/tender/", "/tender-detail/"))
    if "bidassist.com" in parsed.netloc:
        return "/detail-" in path or "-tenders/" in path or "-tender/" in path
    return len(path) > 2


def _extract_date_text(text: str) -> str:
    patterns = (
        r"(?:Closing Date|Due Date|Deadline|Bid End Date|Last Date)\s*:?\s*([0-9]{1,2}\s+[A-Za-z]{3,9},?\s+[0-9]{4})",
        r"(?:Closing Date|Due Date|Deadline|Bid End Date|Last Date)\s*:?\s*([0-9]{1,2}[-/.][0-9]{1,2}[-/.][0-9]{2,4})",
        r"(?:Closing Date|Due Date|Deadline|Bid End Date|Last Date)\s*:?\s*([0-9]{1,2}-[A-Za-z]{3,9}-[0-9]{4})",
        r"\b[0-9]{1,2}\s+[A-Za-z]{3,9}\s+[0-9]{4}\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            return match.group(1) if match.lastindex else match.group(0)
    return ""


def _find_candidate_anchors(
    html: str, base_url: str, keyword: str = ""
) -> List[tuple[str, str, str]]:
    """Return list of (title, href, context_text) for anchors likely to be printing tender notices."""
    if not _BS4_AVAILABLE or not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    anchors = []
    seen_hrefs = set()
    kw_target = keyword.strip().casefold()
    for a in soup.find_all("a", href=True):
        href = a.get("href", "").strip()
        if not href or not _is_valid_newspaper_tender_link(href, base_url):
            continue
        text = (a.get_text(" ", strip=True) or "").strip()
        if not text or len(text) < 8:
            continue
        lowered_text = text.casefold()
        if any(lowered_text.startswith(b) for b in GENERIC_BOILERPLATE_STARTS):
            continue
        parent = a.find_parent(["tr", "li", "article", "section"]) or a
        context = " ".join(parent.get_text(" ", strip=True).split())
        combined = f"{text} {context}".casefold()
        if not any(k.casefold() in combined for k in NOTICE_KEYWORDS):
            continue
        # Filter for printing relevance and matching target keywords
        if kw_target:
            if kw_target not in combined and not any(k.casefold() in combined for k in PRINT_KEYWORDS):
                continue
        elif not any(k.casefold() in combined for k in PRINT_KEYWORDS):
            continue

        full_href = urljoin(base_url, href)
        if full_href in seen_hrefs:
            continue
        seen_hrefs.add(full_href)
        anchors.append((text, full_href, context))
    return anchors


class _NewspaperWorker(BaseFetcher):
    def fetch(self, keyword: str) -> list[dict]:
        return []

    def build(
        self,
        *,
        title: str,
        portal_source: str,
        portal_url: str,
        context: str,
        keyword_hit: str,
        state: str | None = None,
        ref_number: str | None = None,
    ) -> dict:
        if not ref_number:
            nit_match = re.search(
                r"\b(?:NIT|Tender\s*No\.?|Ref\.?\s*No\.?)\s*[:\-]?\s*([A-Za-z0-9/\-_]+)",
                f"{title} {context}",
                flags=re.IGNORECASE,
            )
            if nit_match:
                ref_number = nit_match.group(1).upper()
            else:
                clean_src = re.sub(r"[^A-Za-z0-9]", "", portal_source).upper()
                h = abs(hash(f"{portal_source}:{portal_url}:{title}")) % 10000000
                ref_number = f"{clean_src}-{h:07d}"

        final_title = title
        if len(final_title) < 15 and len(context) > len(final_title):
            final_title = context[:150]

        deadline_raw = _extract_date_text(f"{final_title} {context}")
        if not deadline_raw:
            from datetime import datetime, timezone, timedelta
            now_dt = datetime.now(timezone.utc) + timedelta(days=14)
            deadline_raw = now_dt.strftime("%d %b %Y")

        rec = self.build_record(
            ref_number=ref_number,
            title=final_title,
            organisation=portal_source,
            state=state,
            portal_source=portal_source,
            deadline_raw=deadline_raw,
            value_raw="",
            portal_url=portal_url,
            keyword_hit=keyword_hit,
            tender_id=None,
            link_verified=False,
        )
        rec["link_type"] = "newspaper"
        return rec


NEWSPAPER_SEARCH_ALIASES: dict[str, tuple[str, ...]] = {
    "Dainik Bhaskar": ("Bhaskar", "Dainik Bhaskar"),
    "Nai Dunia": ("Nai Dunia", "Naidunia"),
    "Patrika": ("Patrika", "Rajasthan Patrika"),
    "Dainik Jagran": ("Jagran", "Dainik Jagran"),
    "Nav Bharat": ("Navbharat", "Nav Bharat"),
    "Deshbandhu": ("Deshbandhu", "Desh Bandhu"),
    "Raj Express": ("Raj Express", "RajExpress"),
    "Peoples Samachar": ("Peoples Samachar", "People Samachar"),
    "Dabang Dunia": ("Dabang Dunia", "DabangDunia"),
    "Free Press Journal": ("Free Press", "Free Press Journal", "FreePress"),
    "Pradesh Today": ("Pradesh Today", "PradeshToday"),
    "Agniban": ("Agniban", "Agni Ban"),
    "Nav Swadesh": ("Nav Swadesh", "NavSwadesh"),
    "Swadesh": ("Swadesh",),
    "Hari Bhoomi": ("Haribhoomi", "Hari Bhoomi"),
    "Amar Ujala": ("Amar Ujala", "AmarUjala"),
}


def _scrape_generic_newspaper(
    portal_source: str,
    urls: list[str],
    keyword: str,
    state: str = "Madhya Pradesh",
) -> list[dict]:
    try:
        worker = _NewspaperWorker()
        tenders = []
        seen_keys = set()

        aliases = NEWSPAPER_SEARCH_ALIASES.get(portal_source, (portal_source,))
        search_urls = []
        for alias in aliases:
            search_urls.append(
                f"https://tenderdekho.com/tenders?search={quote_plus(alias)}"
            )
            if keyword:
                search_urls.append(
                    f"https://tenderdekho.com/tenders?search={quote_plus(alias)}+{quote_plus(keyword)}"
                )
            search_urls.append(
                f"https://bidassist.com/all-tenders/active?search={quote_plus(alias)}"
            )
        search_urls.extend(urls)

        for url in search_urls:
            try:
                html = _fetch_html(url)
            except Exception:
                continue
            for title, href, context in _find_candidate_anchors(html, url, keyword=keyword):
                title_key = title.strip().casefold()
                href_key = href.strip().casefold()
                if not title_key or title_key in seen_keys or href_key in seen_keys:
                    continue
                seen_keys.add(title_key)
                seen_keys.add(href_key)
                tenders.append(
                    worker.build(
                        title=title,
                        portal_source=portal_source,
                        portal_url=href,
                        context=context,
                        keyword_hit=keyword,
                        state=state,
                    )
                )
            if tenders:
                break
        return tenders
    except Exception as exc:
        print(f"scrape error for {portal_source}: {exc}")
        return []


# ── MP & Regional Newspapers ───────────────────────────────────────────────

def scrape_bhaskar(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "Dainik Bhaskar",
        ["https://www.bhaskar.com/tenders", "https://www.bhaskar.com/local/", "https://www.bhaskar.com/epaper/"],
        keyword,
        state="Madhya Pradesh",
    )


def scrape_naidunia(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "Nai Dunia",
        ["https://www.naidunia.com/tenders", "https://naidunia.com/epaper", "https://epaper.naidunia.com/"],
        keyword,
        state="Madhya Pradesh",
    )


def scrape_patrika(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "Patrika",
        ["https://www.patrika.com/tenders", "https://www.patrika.com/epaper/", "https://epaper.patrika.com/"],
        keyword,
        state="Madhya Pradesh",
    )


def scrape_jagran(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "Dainik Jagran",
        ["https://www.jagran.com/tenders", "https://epaper.jagran.com/"],
        keyword,
        state="Madhya Pradesh",
    )


def scrape_navbharat(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "Nav Bharat",
        ["https://navbharattimes.indiatimes.com/tenders", "https://www.navbharat.com/tenders", "https://epaper.navbharat.com/"],
        keyword,
        state="Madhya Pradesh",
    )


def scrape_deshbandhu(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "Deshbandhu",
        ["https://deshbandhu.co.in/tenders", "https://deshbandhu.co.in/", "https://epaper.deshbandhu.co.in/"],
        keyword,
        state="Madhya Pradesh",
    )


def scrape_rajexpress(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "Raj Express",
        ["https://www.rajexpress.co/tenders", "https://www.rajexpress.co/", "https://rajexpress.co/epaper"],
        keyword,
        state="Madhya Pradesh",
    )


def scrape_peoplessamachar(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "Peoples Samachar",
        ["https://peoplessamachar.in/tenders", "https://peoplessamachar.in/", "https://epaper.peoplessamachar.in/"],
        keyword,
        state="Madhya Pradesh",
    )


def scrape_dabangdunia(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "Dabang Dunia",
        ["https://dabangdunia.co/tenders", "https://dabangdunia.co/", "https://epaper.dabangdunia.co/"],
        keyword,
        state="Madhya Pradesh",
    )


def scrape_freepressjournal(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "Free Press Journal",
        ["https://www.freepressjournal.in/tenders", "https://www.freepressjournal.in/bhopal", "https://www.freepressjournal.in/indore", "https://epaper.freepressjournal.in/"],
        keyword,
        state="Madhya Pradesh",
    )


def scrape_pradeshtoday(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "Pradesh Today",
        ["https://pradeshtoday.com/tenders", "https://pradeshtoday.com/", "https://epaper.pradeshtoday.com/"],
        keyword,
        state="Madhya Pradesh",
    )


def scrape_agniban(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "Agniban",
        ["https://agniban.com/tenders", "https://agniban.com/", "https://epaper.agniban.com/"],
        keyword,
        state="Madhya Pradesh",
    )


def scrape_navswadesh(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "Nav Swadesh",
        ["https://navswadesh.com/tenders", "https://navswadesh.com/", "https://epaper.navswadesh.com/"],
        keyword,
        state="Madhya Pradesh",
    )


def scrape_swadesh(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "Swadesh",
        ["https://swadeshnews.in/tenders", "https://swadeshnews.in/", "https://swadesh.net.in/"],
        keyword,
        state="Madhya Pradesh",
    )


def scrape_haribhoomi(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "Hari Bhoomi",
        ["https://www.haribhoomi.com/tenders", "https://www.haribhoomi.com/", "https://epaper.haribhoomi.com/"],
        keyword,
        state="Madhya Pradesh",
    )


def scrape_amarujala(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "Amar Ujala",
        ["https://www.amarujala.com/tenders", "https://epaper.amarujala.com/"],
        keyword,
        state="Uttar Pradesh",
    )


# ── National English Newspapers ───────────────────────────────────────────

def scrape_toi(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "TOI Tenders",
        ["https://timesofindia.indiatimes.com/tenders"],
        keyword,
        state="Delhi",
    )


def scrape_ht(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "HT Tenders",
        ["https://hindustantimes.com/classifieds/tenders"],
        keyword,
        state="Delhi",
    )


def scrape_et(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "ET Tenders",
        ["https://economictimes.indiatimes.com/tenders"],
        keyword,
        state="Delhi",
    )


def scrape_thehindu(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "The Hindu Tenders",
        ["https://thehindu.com/classifieds/tenders"],
        keyword,
        state="Tamil Nadu",
    )


# ── Notice Aggregators ───────────────────────────────────────────────────

def scrape_tendernotice(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "Tender Notice India",
        ["https://tendernotice.co.in"],
        keyword,
        state="Madhya Pradesh",
    )


def scrape_indiatendernotice(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "India Tender Notice",
        ["https://indiatendernotice.com"],
        keyword,
        state="Madhya Pradesh",
    )


def scrape_publicnotice(keyword: str) -> list[dict]:
    return _scrape_generic_newspaper(
        "Public Notice India",
        ["https://publicnotice.co.in"],
        keyword,
        state="Madhya Pradesh",
    )


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
    "scrape_deshbandhu",
    "scrape_rajexpress",
    "scrape_peoplessamachar",
    "scrape_dabangdunia",
    "scrape_freepressjournal",
    "scrape_pradeshtoday",
    "scrape_agniban",
    "scrape_navswadesh",
    "scrape_swadesh",
    "scrape_haribhoomi",
    "scrape_tendernotice",
    "scrape_indiatendernotice",
    "scrape_publicnotice",
]
