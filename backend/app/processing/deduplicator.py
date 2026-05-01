from datetime import datetime, timezone

import pandas as pd
from rapidfuzz import fuzz

from app.schemas import TenderCreate


def deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        print("deduplicate removed 0 duplicates")
        return df.copy()

    before = len(df)
    unique = df.drop_duplicates(subset="ref_number", keep="first").copy()
    unique["_original_index"] = unique.index
    unique["_fetched_sort"] = unique["fetched_at"].map(parse_fetched_at)

    remove_indices: set[int] = set()
    for _portal, group in unique.groupby("portal_source", dropna=False):
        kept: list[tuple[int, str]] = []
        ordered = group.sort_values(
            by=["_fetched_sort", "_original_index"],
            ascending=[True, True],
            kind="mergesort",
        )
        for index, row in ordered.iterrows():
            title = str(row.get("title") or "").casefold()
            if any(
                fuzz.token_sort_ratio(title, kept_title) > 88 for _, kept_title in kept
            ):
                remove_indices.add(index)
                continue
            kept.append((index, title))

    deduped = unique.drop(index=remove_indices)
    removed = before - len(deduped)
    print(f"deduplicate removed {removed} duplicates")
    return (
        deduped.sort_values("_original_index")
        .drop(columns=["_original_index", "_fetched_sort"])
        .reset_index(drop=True)
    )


def parse_fetched_at(value: object) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        return datetime.max.replace(tzinfo=timezone.utc)
    return parsed.to_pydatetime()


def tender_fingerprint(tender: TenderCreate) -> str:
    key = f"{tender.source}:{tender.external_id}".casefold()
    return " ".join(key.split())


def deduplicate_tenders(
    tenders: list[TenderCreate], title_threshold: int = 94
) -> list[TenderCreate]:
    seen: dict[str, TenderCreate] = {}
    unique: list[TenderCreate] = []
    for tender in tenders:
        fingerprint = tender_fingerprint(tender)
        if fingerprint in seen:
            continue
        if any(
            fuzz.token_set_ratio(tender.title, existing.title) >= title_threshold
            for existing in unique
        ):
            continue
        seen[fingerprint] = tender
        unique.append(tender)
    return unique
