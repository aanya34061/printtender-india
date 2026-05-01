from dataclasses import asdict
from datetime import datetime

import dateparser

from app.fetchers.base import RawTender
from app.schemas import TenderCreate


def parse_datetime(value: datetime | str | None) -> datetime | None:
    if value is None or isinstance(value, datetime):
        return value
    return dateparser.parse(value, settings={"RETURN_AS_TIMEZONE_AWARE": True})


def normalise_tender(raw: RawTender) -> TenderCreate:
    payload = asdict(raw)
    payload["title"] = " ".join(raw.title.split())
    payload["deadline"] = parse_datetime(raw.deadline)
    payload["published_at"] = parse_datetime(raw.published_at)
    payload["keywords"] = sorted(set(raw.keywords))
    return TenderCreate(**payload)
