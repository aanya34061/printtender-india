from fastapi import APIRouter, BackgroundTasks

from app.tasks.fetch_job import run_fetch_cycle

router = APIRouter()

_last_count: dict[str, int] = {}


async def _bg_fetch() -> None:
    count = await run_fetch_cycle()
    _last_count["count"] = count


@router.post("/trigger")
async def trigger_fetch(background_tasks: BackgroundTasks) -> dict:
    background_tasks.add_task(_bg_fetch)
    return {"status": "triggered", "message": "Fetch job started in background"}


@router.get("/status")
async def fetch_status() -> dict:
    return {"last_count": _last_count.get("count"), "status": "idle"}
