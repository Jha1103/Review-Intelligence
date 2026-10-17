"""Collect genuine public Groww reviews from Google Play.

Uses google-play-scraper with pagination, retries, and a configurable
date window. Preserves original review IDs, dates, ratings, source
provenance, and exact review text. Never invents per-review URLs.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

# Ensure the project root and src/ are on sys.path when run directly
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
for _p in (ROOT, SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from google_play_scraper import Sort, reviews  # noqa: E402

from config import (  # noqa: E402
    APP_ID,
    CLEANED_COLUMNS,
    COUNTRY,
    DATA_QUALITY_REPORT_JSON,
    DATA_DIR,
    INITIAL_BACKOFF_SECONDS,
    LANG,
    MAX_BACKOFF_SECONDS,
    MAX_RETRIES,
    MAX_REVIEWS,
    PAGINATION_SIZE,
    RAW_COLUMNS,
    RAW_REVIEWS_CSV,
    SOURCE_NAME,
    SOURCE_URL,
    WEEKS_BACK,
    default_window_start,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("collect_reviews")


def _parse_review_date(raw: Any) -> datetime | None:
    """Parse a review date from google-play-scraper into a UTC datetime."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        dt = raw
    else:
        try:
            dt = datetime.fromisoformat(str(raw))
        except (ValueError, TypeError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _fetch_page(
    continuation_token: str | None,
    count: int,
    retries_left: int,
) -> tuple[list[dict[str, Any]], str | None, bool]:
    """Fetch one page of reviews with retry/backoff.

    Returns (reviews, next_continuation_token, success).
    """
    attempt = 0
    while attempt < MAX_RETRIES:
        try:
            result = reviews(
                app_id=APP_ID,
                lang=LANG,
                country=COUNTRY,
                sort=Sort.NEWEST,
                count=count,
                filter_score_with=None,
                filter_device_with=None,
                continuation_token=continuation_token,
            )
            # google-play-scraper returns (list, continuation_token)
            if isinstance(result, tuple) and len(result) == 2:
                page_reviews, next_token = result
            else:
                page_reviews = result
                next_token = None
            return list(page_reviews), next_token, True
        except Exception as exc:  # noqa: BLE001
            attempt += 1
            if attempt >= MAX_RETRIES:
                logger.error(
                    "Failed to fetch page after %d attempts: %s", MAX_RETRIES, exc
                )
                return [], None, False
            wait = min(
                MAX_BACKOFF_SECONDS,
                INITIAL_BACKOFF_SECONDS * (2 ** (attempt - 1)),
            )
            logger.warning(
                "Fetch attempt %d/%d failed (%s); retrying in %.1fs",
                attempt,
                MAX_RETRIES,
                exc,
                wait,
            )
            time.sleep(wait)
    return [], None, False


def collect_reviews(
    window_start: datetime | None = None,
    max_reviews: int | None = None,
    pagination_size: int | None = None,
) -> dict[str, Any]:
    """Collect public Groww reviews within the configured window.

    Returns a dict with raw rows, quality metrics, and pagination info.
    """
    if window_start is None:
        window_start = default_window_start()
    if max_reviews is None:
        max_reviews = MAX_REVIEWS
    if pagination_size is None:
        pagination_size = PAGINATION_SIZE

    now_utc = datetime.now(timezone.utc)
    collected_at = now_utc.isoformat()

    logger.info(
        "Starting collection: app=%s, window_start=%s, max_reviews=%s, page_size=%s",
        APP_ID,
        window_start.isoformat(),
        max_reviews if max_reviews else "unlimited",
        pagination_size,
    )

    raw_rows: list[dict[str, Any]] = []
    continuation_token: str | None = None
    total_fetched = 0
    total_in_window = 0
    pagination_ended_naturally = True
    limited_by_cap = False

    while True:
        # Determine how many to request this page
        if max_reviews and max_reviews > 0:
            remaining = max_reviews - total_fetched
            if remaining <= 0:
                limited_by_cap = True
                break
            page_count = min(pagination_size, remaining)
        else:
            page_count = pagination_size

        page_reviews, next_token, success = _fetch_page(
            continuation_token, page_count, MAX_RETRIES
        )

        if not success:
            pagination_ended_naturally = False
            logger.error("Stopping collection due to repeated fetch failures.")
            break

        if not page_reviews:
            logger.info("No more reviews returned; pagination ended naturally.")
            pagination_ended_naturally = True
            break

        total_fetched += len(page_reviews)
        logger.info(
            "Fetched page of %d reviews (running total: %d)",
            len(page_reviews),
            total_fetched,
        )

        for rev in page_reviews:
            review_id = rev.get("reviewId")
            raw_date = rev.get("at")
            review_date = _parse_review_date(raw_date)
            rating = rev.get("score")
            text = rev.get("content") or ""
            app_version = rev.get("reviewCreatedVersion")

            # Skip reviews missing essential identity fields
            if not review_id:
                continue
            if review_date is None:
                continue

            # Apply date window filter
            if review_date < window_start:
                continue

            total_in_window += 1

            raw_rows.append(
                {
                    "review_id": review_id,
                    "review_date": review_date.isoformat(),
                    "rating": rating if rating is not None else "",
                    "original_review_text": text,
                    "source": SOURCE_NAME,
                    "source_url": SOURCE_URL,
                    "collected_at": collected_at,
                    "app_version": app_version if app_version else "",
                }
            )

        continuation_token = next_token
        if not continuation_token:
            logger.info("No continuation token returned; pagination ended naturally.")
            pagination_ended_naturally = True
            break

        # Safety: stop if we seem to be looping without progress
        if len(raw_rows) >= 10000 and not max_reviews:
            logger.warning(
                "Reached 10,000 collected reviews; stopping to avoid unbounded pagination."
            )
            pagination_ended_naturally = False
            limited_by_cap = True
            break

    # Sort by review_date descending (newest first)
    raw_rows.sort(key=lambda r: r["review_date"], reverse=True)

    # Deduplicate by review_id (preserve first occurrence = newest)
    seen_ids: set[str] = set()
    deduped_rows: list[dict[str, Any]] = []
    duplicates_removed = 0
    for row in raw_rows:
        rid = row["review_id"]
        if rid in seen_ids:
            duplicates_removed += 1
            continue
        seen_ids.add(rid)
        deduped_rows.append(row)

    logger.info(
        "Collection complete: fetched=%d, in_window=%d, deduped=%d, duplicates_removed=%d",
        total_fetched,
        total_in_window,
        len(deduped_rows),
        duplicates_removed,
    )

    quality_report = {
        "product_name": "Groww",
        "collection_timestamp": collected_at,
        "configured_date_window_weeks": WEEKS_BACK,
        "window_start_utc": window_start.isoformat(),
        "window_end_utc": now_utc.isoformat(),
        "total_reviews_fetched": total_fetched,
        "eligible_reviews_in_date_window": total_in_window,
        "duplicate_reviews_removed": duplicates_removed,
        "invalid_empty_reviews_removed": 0,  # filled by clean_reviews.py
        "final_cleaned_reviews": 0,  # filled by clean_reviews.py
        "earliest_eligible_review_date": (
            min(r["review_date"] for r in deduped_rows) if deduped_rows else ""
        ),
        "latest_eligible_review_date": (
            max(r["review_date"] for r in deduped_rows) if deduped_rows else ""
        ),
        "rating_distribution": _rating_distribution(deduped_rows),
        "reviews_requiring_pii_redaction": 0,  # filled by clean_reviews.py
        "pagination_ended_naturally": pagination_ended_naturally,
        "collection_limited_by_cap": limited_by_cap,
        "coverage_limitations": _coverage_limitations(
            pagination_ended_naturally, limited_by_cap, total_fetched, total_in_window
        ),
    }

    return {
        "rows": deduped_rows,
        "quality_report": quality_report,
        "collected_at": collected_at,
    }


def _rating_distribution(rows: list[dict[str, Any]]) -> dict[str, int]:
    """Count reviews per star rating (1-5)."""
    dist = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    for row in rows:
        r = row.get("rating")
        if r in dist:
            dist[r] += 1
    return dist


def _coverage_limitations(
    ended_naturally: bool,
    limited_by_cap: bool,
    fetched: int,
    in_window: int,
) -> str:
    """Describe any coverage limitations."""
    parts: list[str] = []
    if not ended_naturally:
        parts.append("pagination did not end naturally (collection stopped early)")
    if limited_by_cap:
        parts.append("collection was limited by the configured max review cap")
    if fetched == 0:
        parts.append("no reviews were fetched")
    elif in_window < fetched:
        parts.append(
            f"only {in_window} of {fetched} fetched reviews fall within the date window"
        )
    if not parts:
        return "none identified"
    return "; ".join(parts)


def write_raw_csv(rows: list[dict[str, Any]], path: str = RAW_REVIEWS_CSV) -> None:
    """Write raw collected reviews to CSV."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RAW_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    logger.info("Wrote %d raw reviews to %s", len(rows), path)


def main() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    result = collect_reviews()
    write_raw_csv(result["rows"], RAW_REVIEWS_CSV)

    # Write a preliminary quality report (clean_reviews.py will update it)
    report_path = DATA_QUALITY_REPORT_JSON
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(result["quality_report"], f, indent=2, ensure_ascii=False)
    logger.info("Wrote preliminary quality report to %s", report_path)


if __name__ == "__main__":
    main()
