import asyncio

from fastapi import APIRouter, Header, HTTPException

from app.config import get_settings
from app.sources import LIVE_PORTAL_SOURCES
from app.tasks.fetch_job import FAST_FETCH_KEYWORD_LIMIT

router = APIRouter()

run_fetch_cycle = None
_last_count: dict[str, int] = {}
_running_task: asyncio.Task | None = None
_running_scope: str | None = None

BANK_PORTAL_SOURCES = {
    "PNB Tenders",
    "Canara Bank Tenders",
    "Central Bank of India Tenders",
    "Bank of India Tenders",
    "Indian Bank Tenders",
    "UCO Bank Tenders",
    "Indian Overseas Bank Tenders",
    "LIC Tenders",
}
MP_PORTAL_SOURCES = {"MP Tenders", "eproc.mp.gov.in"}
LIC_PORTAL_SOURCES = {"LIC Tenders"}
LIVE_CRON_PORTAL_SOURCES = set(LIVE_PORTAL_SOURCES)


async def _run_and_store(*, scope: str = "live") -> int:
    global run_fetch_cycle
    if run_fetch_cycle is None:
        from app.tasks.fetch_job import run_fetch_cycle as loaded_run_fetch_cycle

        run_fetch_cycle = loaded_run_fetch_cycle

    normalized_scope = scope.casefold().strip()
    if normalized_scope == "full":
        count = await run_fetch_cycle()
    elif normalized_scope == "lic":
        count = await run_fetch_cycle(
            source_labels=LIC_PORTAL_SOURCES,
            include_newspapers=False,
        )
    elif normalized_scope == "banks":
        count = await run_fetch_cycle(
            source_labels=BANK_PORTAL_SOURCES,
            include_newspapers=False,
        )
    elif normalized_scope in {"cron", "live"}:
        count = await run_fetch_cycle(
            source_labels=LIVE_CRON_PORTAL_SOURCES,
            max_keywords_per_source=FAST_FETCH_KEYWORD_LIMIT,
            include_newspapers=False,
        )
    else:
        count = await run_fetch_cycle(
            source_labels=MP_PORTAL_SOURCES,
            include_newspapers=False,
        )
    _last_count["count"] = count
    from app.api.stats import clear_stats_cache
    from app.api.tenders import clear_tender_list_cache

    clear_stats_cache()
    clear_tender_list_cache()
    return count


@router.post("/trigger")
async def trigger_fetch(scope: str = "live", sync: bool = False) -> dict:
    global _running_task, _running_scope
    normalized_scope = scope.casefold().strip()
    if sync or normalized_scope == "lic":
        count = await _run_and_store(scope=normalized_scope)
        return {
            "status": "completed",
            "scope": normalized_scope,
            "count": count,
        }
    if _running_task is not None and not _running_task.done():
        return {
            "status": "already_running",
            "scope": _running_scope or normalized_scope,
            "count": _last_count.get("count"),
        }

    async def runner() -> None:
        try:
            await _run_and_store(scope=normalized_scope)
        finally:
            global _running_scope
            _running_scope = None

    _running_scope = normalized_scope
    _running_task = asyncio.create_task(runner())
    return {
        "status": "triggered",
        "scope": normalized_scope,
        "count": _last_count.get("count"),
    }


@router.get("/cron")
async def cron_fetch(
    scope: str = "live", authorization: str | None = Header(default=None)
) -> dict:
    expected = get_settings().CRON_SECRET
    if expected and authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Unauthorized cron request")
    normalized_scope = scope.casefold().strip()
    count = await _run_and_store(scope=normalized_scope)
    return {"status": "completed", "scope": normalized_scope, "count": count}


@router.get("/mail-cron")
async def mail_cron(authorization: str | None = Header(default=None)) -> dict:
    expected = get_settings().CRON_SECRET
    if expected and authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Unauthorized cron request")

    from app.tasks.fetch_job import send_scheduled_subscriber_mails

    result = await send_scheduled_subscriber_mails()
    return {"status": "completed", **result}


@router.get("/status")
async def fetch_status() -> dict:
    running = _running_task is not None and not _running_task.done()
    return {
        "last_count": _last_count.get("count"),
        "status": "running" if running else "idle",
        "scope": _running_scope if running else None,
    }


@router.api_route("/cache-clear", methods=["GET", "POST"])
async def clear_fetch_cache() -> dict:
    from app.api.stats import clear_stats_cache
    from app.api.tenders import clear_tender_list_cache
    from app.fallback_mp import _SEARCH_CACHE
    from app.fetchers.banks import HTML_CACHE

    clear_tender_list_cache()
    clear_stats_cache()
    HTML_CACHE.clear()
    _SEARCH_CACHE.clear()
    return {"status": "ok", "message": "All backend caches cleared"}
