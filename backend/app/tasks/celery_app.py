try:
    from celery import Celery
    from celery.schedules import crontab
except ImportError:
    Celery = None
    crontab = None

from app.config import get_settings

settings = get_settings()


class _NoopCeleryApp:
    def task(self, *args, **kwargs):
        def decorator(func):
            return func

        return decorator


if settings.REDIS_URL and Celery is not None and crontab is not None:
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
            },
            "send-morning-subscriber-mails": {
                "task": "app.tasks.fetch_job.send_scheduled_subscriber_mails_task",
                "schedule": crontab(hour=9, minute=0),
            },
            "send-afternoon-subscriber-mails": {
                "task": "app.tasks.fetch_job.send_scheduled_subscriber_mails_task",
                "schedule": crontab(hour=13, minute=30),
            },
            "send-evening-subscriber-mails": {
                "task": "app.tasks.fetch_job.send_scheduled_subscriber_mails_task",
                "schedule": crontab(hour=19, minute=0),
            }
        },
    )
else:
    celery_app = _NoopCeleryApp()
