"""Clean and deduplicate collected Groww reviews.

- Deduplicates by original review ID.
- Filters to the configured 12-week window.
- Handles missing/invalid dates and ratings.
- Removes empty reviews (without dropping short fee complaints).
- Normalizes whitespace.
- Redacts PII (emails, phones, PAN-like patterns) in cleaned_review_text only.
- Preserves original_review_text privately; never writes PII to the public sample.
- Tracks exclusion reasons without recording sensitive content.
"""

from __future__ import annotations

import csv
import json
import logging
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

# Ensure the project root and src/ are on sys.path when run directly
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
for _p in (ROOT, SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import (  # noqa: E402
    APP_ID,
    CLEANED_COLUMNS,
    CLEANED_REVIEWS_CSV,
    COUNTRY,
    DATA_QUALITY_REPORT_JSON,
    DATA_DIR,
    LANG,
    RAW_COLUMNS,
    RAW_REVIEWS_CSV,
    REVIEWS_SAMPLE_CSV,
    SAMPLE_SIZE,
    SOURCE_NAME,
    SOURCE_URL,
    WEEKS_BACK,
    default_window_start,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("clean_reviews")

# --- PII detection patterns ---
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
PHONE_RE = re.compile(r"\b(?:\+?91[\s-]?)?[6-9]\d{9}\b")  # Indian mobile numbers
PAN_RE = re.compile(r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b")  # PAN-like: ABCDE1234F
ACCOUNT_RE = re.compile(r"\b\d{9,18}\b")  # long numeric sequences (possible account numbers)
UPI_RE = re.compile(r"\b[A-Za-z0-9._-]+@[A-Za-z]+\b")  # UPI-style handles

PII_PATTERNS = [
    ("email", EMAIL_RE),
    ("phone", PHONE_RE),
    ("pan", PAN_RE),
    ("upi", UPI_RE),
    ("long_number", ACCOUNT_RE),
]

REDACTION_TOKEN = "[REDACTED]"


def _redact_pii(text: str) -> tuple[str, bool]:
    """Redact PII patterns from text. Returns (redacted_text, was_redacted)."""
    if not text:
        return text, False
    redacted = text
    was_redacted = False
    for _label, pattern in PII_PATTERNS:
        new_text, n = pattern.subn(REDACTION_TOKEN, redacted)
        if n > 0:
            was_redacted = True
            redacted = new_text
    return redacted, was_redacted


def _is_empty_review(text: str) -> bool:
    """Return True if the review text is empty or whitespace-only."""
    return not text or not text.strip()


def _parse_date(raw: Any) -> datetime | None:
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


def _normalize_whitespace(text: str) -> str:
    """Collapse runs of whitespace into single spaces, strip ends."""
    return re.sub(r"\s+", " ", text).strip()


def clean_reviews(
    raw_path: str = RAW_REVIEWS_CSV,
    window_start: datetime | None = None,
    cleaned_path: str = CLEANED_REVIEWS_CSV,
    sample_path: str = REVIEWS_SAMPLE_CSV,
    report_path: str = DATA_QUALITY_REPORT_JSON,
    exclusion_path: str | None = None,
) -> dict[str, Any]:
    """Read raw CSV, clean/dedupe/filter, write cleaned CSV + sample + quality report."""
    if window_start is None:
        window_start = default_window_start()

    if not os.path.exists(raw_path):
        raise FileNotFoundError(f"Raw reviews CSV not found: {raw_path}")

    # Load previous quality report if it exists
    quality_report: dict[str, Any] = {}
    if report_path and os.path.exists(report_path):
        with open(report_path, "r", encoding="utf-8") as f:
            quality_report = json.load(f)

    # Read raw rows
    raw_rows: list[dict[str, Any]] = []
    with open(raw_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            raw_rows.append(row)

    total_raw = len(raw_rows)
    logger.info("Loaded %d raw reviews from %s", total_raw, raw_path)

    # --- Deduplicate by review_id (preserve first occurrence) ---
    seen_ids: set[str] = set()
    deduped: list[dict[str, Any]] = []
    duplicates_removed = 0
    for row in raw_rows:
        rid = (row.get("review_id") or "").strip()
        if not rid:
            duplicates_removed += 1  # no ID = cannot track; treat as dropped
            continue
        if rid in seen_ids:
            duplicates_removed += 1
            continue
        seen_ids.add(rid)
        deduped.append(row)

    logger.info("After dedup: %d reviews (removed %d duplicates)", len(deduped), duplicates_removed)

    # --- Date window filter ---
    in_window: list[dict[str, Any]] = []
    out_of_window = 0
    invalid_dates = 0
    for row in deduped:
        rd = _parse_date(row.get("review_date"))
        if rd is None:
            invalid_dates += 1
            continue
        if rd < window_start:
            out_of_window += 1
            continue
        in_window.append(row)

    logger.info(
        "Date filter: %d in window, %d out of window, %d invalid dates",
        len(in_window), out_of_window, invalid_dates,
    )

    # --- Clean each review ---
    cleaned_rows: list[dict[str, Any]] = []
    empty_removed = 0
    invalid_rating_removed = 0
    pii_redacted_count = 0
    exclusion_log: list[dict[str, str]] = []

    for row in in_window:
        rid = (row.get("review_id") or "").strip()
        raw_text = row.get("original_review_text") or ""
        rating_raw = (row.get("rating") or "").strip()

        # Rating validation: must be 1-5
        try:
            rating_val = int(float(rating_raw)) if rating_raw else None
        except (ValueError, TypeError):
            rating_val = None
        if rating_val is None or rating_val < 1 or rating_val > 5:
            invalid_rating_removed += 1
            exclusion_log.append(
                {"review_id": rid, "reason": "invalid_or_missing_rating"}
            )
            continue

        # Empty review check (do NOT remove short reviews automatically)
        if _is_empty_review(raw_text):
            empty_removed += 1
            exclusion_log.append(
                {"review_id": rid, "reason": "empty_or_whitespace_review"}
            )
            continue

        # Normalize whitespace
        cleaned_text = _normalize_whitespace(raw_text)

        # PII redaction on cleaned text only
        redacted_text, was_redacted = _redact_pii(cleaned_text)
        if was_redacted:
            pii_redacted_count += 1

        cleaned_rows.append(
            {
                "review_id": rid,
                "review_date": row.get("review_date", ""),
                "rating": str(rating_val),
                "original_review_text": raw_text,
                "cleaned_review_text": redacted_text,
                "source": row.get("source", SOURCE_NAME),
                "source_url": row.get("source_url", SOURCE_URL),
                "collected_at": row.get("collected_at", ""),
                "app_version": row.get("app_version", ""),
                "pii_redacted": "yes" if was_redacted else "no",
                "exclusion_reason": "",  # not excluded
            }
        )

    logger.info(
        "Cleaning complete: %d cleaned reviews, %d empty removed, %d invalid rating removed, %d PII redacted",
        len(cleaned_rows), empty_removed, invalid_rating_removed, pii_redacted_count,
    )

    # --- Write cleaned CSV ---
    os.makedirs(os.path.dirname(cleaned_path), exist_ok=True)
    with open(cleaned_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CLEANED_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in cleaned_rows:
            writer.writerow(row)
    logger.info("Wrote %d cleaned reviews to %s", len(cleaned_rows), cleaned_path)

    # --- Write sanitized sample CSV (no PII, no original text with PII) ---
    sample_rows = cleaned_rows[:SAMPLE_SIZE]
    sample_columns = [
        "review_id",
        "review_date",
        "rating",
        "cleaned_review_text",
        "source",
        "source_url",
        "collected_at",
        "app_version",
        "pii_redacted",
    ]
    os.makedirs(os.path.dirname(sample_path), exist_ok=True)
    with open(sample_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=sample_columns, extrasaction="ignore")
        writer.writeheader()
        for row in sample_rows:
            writer.writerow({k: row.get(k, "") for k in sample_columns})
    logger.info("Wrote %d sanitized sample rows to %s", len(sample_rows), sample_path)

    # --- Rating distribution ---
    rating_dist = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    for row in cleaned_rows:
        r = row.get("rating", "")
        if r in rating_dist:
            rating_dist[r] += 1

    # --- Date range ---
    dates = [
        _parse_date(r.get("review_date")) for r in cleaned_rows
    ]
    dates = [d for d in dates if d is not None]
    earliest = min(dates).isoformat() if dates else ""
    latest = max(dates).isoformat() if dates else ""

    # --- Update quality report ---
    quality_report.update(
        {
            "product_name": "Groww",
            "collection_timestamp": quality_report.get(
                "collection_timestamp", datetime.now(timezone.utc).isoformat()
            ),
            "configured_date_window_weeks": WEEKS_BACK,
            "window_start_utc": window_start.isoformat(),
            "window_end_utc": datetime.now(timezone.utc).isoformat(),
            "total_reviews_fetched": quality_report.get("total_reviews_fetched", total_raw),
            "eligible_reviews_in_date_window": quality_report.get(
                "eligible_reviews_in_date_window", len(in_window)
            ),
            "duplicate_reviews_removed": duplicates_removed,
            "invalid_empty_reviews_removed": empty_removed + invalid_rating_removed + invalid_dates + out_of_window,
            "final_cleaned_reviews": len(cleaned_rows),
            "earliest_eligible_review_date": earliest,
            "latest_eligible_review_date": latest,
            "rating_distribution": rating_dist,
            "reviews_requiring_pii_redaction": pii_redacted_count,
            "pagination_ended_naturally": quality_report.get(
                "pagination_ended_naturally", True
            ),
            "collection_limited_by_cap": quality_report.get(
                "collection_limited_by_cap", False
            ),
            "coverage_limitations": quality_report.get(
                "coverage_limitations", "none identified"
            ),
            "exclusion_log_count": len(exclusion_log),
        }
    )

    if report_path:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(quality_report, f, indent=2, ensure_ascii=False)
        logger.info("Wrote updated quality report to %s", report_path)

    # Write exclusion log separately (not committed, no sensitive content)
    if exclusion_path is None:
        exclusion_path = os.path.join(DATA_DIR, "exclusions.log")
    with open(exclusion_path, "w", encoding="utf-8") as f:
        for entry in exclusion_log:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    logger.info("Wrote %d exclusion entries to %s (no sensitive content)", len(exclusion_log), exclusion_path)

    return {
        "cleaned_rows": cleaned_rows,
        "quality_report": quality_report,
        "exclusion_log": exclusion_log,
    }


def main() -> None:
    result = clean_reviews()
    logger.info(
        "Clean pipeline done: %d final cleaned reviews",
        len(result["cleaned_rows"]),
    )


if __name__ == "__main__":
    main()
