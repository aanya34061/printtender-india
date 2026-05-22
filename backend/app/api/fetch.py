from fastapi import APIRouter, Header, HTTPException

from app.config import get_settings
from app.tasks.fetch_job import run_fetch_cycle

router = APIRouter()

_last_count: dict[str, int] = {}

async def _run_and_store() -> int:
    count = await run_fetch_cycle()
    _last_count["count"] = count
    return count


@router.post("/trigger")
async def trigger_fetch() -> dict:
    count = await _run_and_store()
    return {"status": "triggered", "count": count}


@router.get("/cron")
async def cron_fetch(authorization: str | None = Header(default=None)) -> dict:
    expected = get_settings().CRON_SECRET
    if expected and authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Unauthorized cron request")
    count = await _run_and_store()
    return {"status": "completed", "count": count}


@router.get("/status")
async def fetch_status() -> dict:
    return {"last_count": _last_count.get("count"), "status": "idle"}
