import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


PRINT_KEYWORDS = [
    "printing",
    "offset printing",
    "digital printing",
    "flexographic printing",
    "screen printing",
    "stationery printing",
    "brochure printing",
    "calendar printing",
    "book printing",
    "textbook printing",
    "government forms printing",
    "gazette printing",
    "security printing",
    "ballot paper",
    "postal stationery",
    "label printing",
    "packaging printing",
    "flex printing",
    "banner printing",
    "toner cartridge",
    "ink supply",
    "printing machine",
    "offset machine",
]

PRINTING_KEYWORDS = PRINT_KEYWORDS

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
REQUEST_HEADERS = {"User-Agent": USER_AGENT}
RESULT_KEYS = (
    "ref_number",
    "title",
    "organisation",
    "state",
    "portal_source",
    "deadline_raw",
    "value_raw",
    "portal_url",
    "keyword_hit",
    "fetched_at",
)


@dataclass
class RawTender:
    source: str
    external_id: str
    title: str
    buyer: str | None = None
    state: str | None = None
    category: str | None = None
    estimated_value: float | None = None
    deadline: datetime | str | None = None
    published_at: datetime | str | None = None
    tender_url: str | None = None
    keywords: list[str] = field(default_factory=list)
    raw_payload: dict[str, Any] = field(default_factory=dict)


class BaseFetcher(ABC):
    def __init__(self, keywords: list[str] | None = None) -> None:
        self.keywords = keywords or PRINT_KEYWORDS

    @abstractmethod
    def fetch(self, keyword: str) -> list[dict]:
        raise NotImplementedError

    def fetch_all_keywords(self) -> list[dict]:
        tenders: list[dict] = []
        for keyword in self.keywords:
            try:
                found = self.fetch(keyword)
            except Exception as exc:
                self.log_result(
                    self.__class__.__name__, keyword, 0, 0, "error", str(exc)
                )
                found = []
            tenders.extend(found)
        return tenders

    def log_result(
        self,
        portal: str,
        keyword: str,
        found: int,
        added: int,
        status: str,
        error: str | None = None,
    ) -> None:
        timestamp = datetime.now(timezone.utc).isoformat()
        message = (
            f"{timestamp} portal={portal} keyword={keyword!r} "
            f"found={found} added={added} status={status}"
        )
        if error:
            message = f"{message} error={error}"
        print(message)

    def wait_between_requests(self) -> None:
        time.sleep(random.uniform(2, 4))

    def build_record(
        self,
        *,
        ref_number: str | None,
        title: str | None,
        organisation: str | None,
        state: str | None,
        portal_source: str,
        deadline_raw: str | None,
        value_raw: str | None,
        portal_url: str | None,
        keyword_hit: str,
    ) -> dict:
        return {
            "ref_number": (ref_number or "").strip(),
            "title": (title or "").strip(),
            "organisation": (organisation or "").strip(),
            "state": (state or "").strip(),
            "portal_source": portal_source,
            "deadline_raw": (deadline_raw or "").strip(),
            "value_raw": (value_raw or "").strip(),
            "portal_url": (portal_url or "").strip(),
            "keyword_hit": keyword_hit,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    def match_keywords(self, text: str) -> list[str]:
        normalized = text.casefold()
        return [
            keyword for keyword in self.keywords if keyword.casefold() in normalized
        ]
