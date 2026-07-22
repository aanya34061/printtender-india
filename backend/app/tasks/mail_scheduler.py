from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.tasks.fetch_job import send_scheduled_subscriber_mails

IST = ZoneInfo("Asia/Kolkata")
SCHEDULED_MAIL_TIMES = ((8, 0),)


def next_scheduled_mail_at(now: datetime | None = None) -> datetime:
    now_ist = (now or datetime.now(IST)).astimezone(IST)
    for hour, minute in SCHEDULED_MAIL_TIMES:
        candidate = now_ist.replace(
            hour=hour, minute=minute, second=0, microsecond=0
        )
        if candidate > now_ist:
            return candidate

    tomorrow = now_ist + timedelta(days=1)
    first_hour, first_minute = SCHEDULED_MAIL_TIMES[0]
    return tomorrow.replace(
        hour=first_hour, minute=first_minute, second=0, microsecond=0
    )


async def run_scheduled_mail_loop() -> None:
    while True:
        target = next_scheduled_mail_at()
        delay_seconds = max(1.0, (target - datetime.now(IST)).total_seconds())
        print(f"scheduled_mail_waiting next_run={target.isoformat()}")
        await asyncio.sleep(delay_seconds)

        try:
            result = await send_scheduled_subscriber_mails()
            print(f"scheduled_mail_completed result={result}")
        except Exception as exc:
            print(f"scheduled_mail_failed error={exc!r}")
