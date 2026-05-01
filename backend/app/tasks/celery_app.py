from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "printtender_india",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    beat_schedule={
        "fetch-all-tenders": {
            "task": "app.tasks.fetch_job.fetch_all_tenders",
            "schedule": settings.FETCH_INTERVAL_HOURS * 3600,
        }
    },
)
