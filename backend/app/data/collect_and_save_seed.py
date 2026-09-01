import asyncio
import json
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.fetchers.cppp import CPPPFetcher
from app.fetchers.gem import GeMFetcher
from app.fetchers.state import StateFetcher
from app.fetchers.mp_portals import scrape_mp_tenders
from app.fetchers.banks import scrape_canara_bank, scrape_lic
from app.fetchers.aggregators import scrape_tenderdekho, scrape_bidassist
from app.fetchers.newspapers import scrape_bhaskar, scrape_patrika, scrape_tendernotice

KEYWORDS = [
    "printing",
    "stationery",
    "books",
    "forms",
    "envelopes",
    "certificates",
    "calendars",
    "brochures",
    "registers",
    "paper",
    "cards",
    "offset printing",
    "digital printing",
    "labels",
    "answer books",
    "visiting cards",
    "slm",
    "study material",
]

scrapers = [
    ("CPPP", lambda kw: CPPPFetcher().fetch(kw)),
    ("GeM", lambda kw: GeMFetcher().fetch(kw)),
    ("State-MP", lambda kw: StateFetcher().fetch(kw, "MP")),
    ("State-UP", lambda kw: StateFetcher().fetch(kw, "UP")),
    ("State-MH", lambda kw: StateFetcher().fetch(kw, "MH")),
    ("State-RJ", lambda kw: StateFetcher().fetch(kw, "RJ")),
    ("MP Tenders", scrape_mp_tenders),
    ("LIC Tenders", scrape_lic),
    ("Canara Bank Tenders", scrape_canara_bank),
    ("TenderDekho", scrape_tenderdekho),
    ("BidAssist", scrape_bidassist),
    ("Dainik Bhaskar", scrape_bhaskar),
    ("Patrika", scrape_patrika),
    ("Tender Notice India", scrape_tendernotice),
]

async def run_scraper(name, fn):
    items = []
    for kw in KEYWORDS:
        try:
            res = await asyncio.to_thread(fn, kw)
            if res:
                items.extend(res)
        except Exception as e:
            pass
    print(f"[{name}] Raw fetched: {len(items)}")
    return items

async def main():
    print("Collecting tenders across all portals...")
    tasks = [run_scraper(name, fn) for name, fn in scrapers]
    results = await asyncio.gather(*tasks)
    
    all_raw = []
    for r in results:
        all_raw.extend(r)
        
    out_path = os.path.join(os.path.dirname(__file__), "seed_tenders.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_raw, f, default=str, indent=2)
        
    print(f"Saved {len(all_raw)} tenders to {out_path}")

if __name__ == "__main__":
    asyncio.run(main())
