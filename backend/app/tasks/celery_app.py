from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery("printtender_india", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.timezone = "Asia/Kolkata"
celery_app.conf.beat_schedule = {
    "fetch-tenders": {
        "task": "app.tasks.fetch_job.fetch_all_sources",
        "schedule": settings.fetch_interval_hours * 60 * 60,
    }
}
