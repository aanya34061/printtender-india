import asyncio
import json
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from app.database import create_tables, run_startup_migrations
from app.processing.normaliser import normalise_tender
from app.processing.deduplicator import deduplicate_tenders
from app.tasks.fetch_job import _upsert_tenders
from app.api.stats import clear_stats_cache
from app.api.tenders import clear_tender_list_cache

async def ingest_seed():
    seed_path = os.path.join(os.path.dirname(__file__), "seed_tenders.json")
    if not os.path.exists(seed_path):
        print("No seed_tenders.json found.")
        return

    with open(seed_path, "r", encoding="utf-8") as f:
        raw_tenders = json.load(f)

    print(f"Loaded {len(raw_tenders)} raw tenders from seed_tenders.json")
    await create_tables()
    await run_startup_migrations()

    normalised = [normalise_tender(r) for r in raw_tenders]
    valid = deduplicate_tenders([t for t in normalised if t is not None])
    print(f"Valid normalized & deduplicated tenders: {len(valid)}")

    new_ids = await _upsert_tenders(valid)
    print(f"Successfully upserted {len(valid)} tenders ({len(new_ids)} new inserted) into database!")
    clear_stats_cache()
    clear_tender_list_cache()

if __name__ == "__main__":
    asyncio.run(ingest_seed())
