import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.fetchers.deeplinks import resolve_link
from app.keywords import PRINT_KEYWORDS, PRINTING_KEYWORDS  # noqa: F401 (re-exported)

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
    "link_type",
    "keyword_hit",
    "tender_id",
    "link_verified",
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
        tender_id: str | None = None,
        link_verified: bool = False,
    ) -> dict:
        resolved_url, link_type = resolve_link(
            portal_source,
            ref_number or "",
            tender_id,
            portal_url,
            link_verified,
        )
        return {
            "ref_number": (ref_number or "").strip(),
            "title": (title or "").strip(),
            "organisation": (organisation or "").strip(),
            "state": (state or "").strip(),
            "portal_source": portal_source,
            "deadline_raw": (deadline_raw or "").strip(),
            "value_raw": (value_raw or "").strip(),
            "portal_url": resolved_url,
            "link_type": link_type,
            "keyword_hit": keyword_hit,
            "tender_id": tender_id,
            "link_verified": link_verified,
            "fetched_at": datetime.now(timezone.utc).isoformat(),
        }

    def match_keywords(self, text: str) -> list[str]:
        normalized = text.casefold()
        return [
            keyword for keyword in self.keywords if keyword.casefold() in normalized
        ]
