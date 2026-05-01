import asyncio
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

PRINTING_KEYWORDS = [
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
    "lamination",
]


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
    raw_payload: dict = field(default_factory=dict)


class BaseFetcher(ABC):
    source_name: str

    def __init__(self, keywords: list[str] | None = None) -> None:
        self.keywords = keywords or PRINTING_KEYWORDS

    async def delay(self) -> None:
        await asyncio.sleep(random.uniform(2, 4))

    def match_keywords(self, text: str) -> list[str]:
        normalized = text.casefold()
        return [keyword for keyword in self.keywords if keyword.casefold() in normalized]

    @abstractmethod
    async def fetch(self) -> list[RawTender]:
        raise NotImplementedError
