"""Configuration for the Groww review data collection pipeline.

All values are configurable via environment variables with sensible defaults.
No secrets are stored here.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone


# --- Google Play configuration ---
APP_ID = os.getenv("GROWW_APP_ID", "com.nextbillion.groww")
LANG = os.getenv("GROWW_LANG", "en")
COUNTRY = os.getenv("GROWW_COUNTRY", "in")
WEEKS_BACK = int(os.getenv("GROWW_WEEKS_BACK", "12"))
MAX_REVIEWS = int(os.getenv("GROWW_MAX_REVIEWS", "0"))  # 0 = no explicit cap
PAGINATION_SIZE = int(os.getenv("GROWW_PAGINATION_SIZE", "200"))

# --- Google Play app URL (source provenance, not per-review links) ---
SOURCE_URL = f"https://play.google.com/store/apps/details?id={APP_ID}"
SOURCE_NAME = "google_play"

# --- Collection window ---
def default_window_start() -> datetime:
    """Default start of the collection window (now minus WEEKS_BACK)."""
    return datetime.now(timezone.utc) - timedelta(weeks=WEEKS_BACK)


# --- Retry configuration ---
MAX_RETRIES = int(os.getenv("GROWW_MAX_RETRIES", "5"))
INITIAL_BACKOFF_SECONDS = float(os.getenv("GROWW_INITIAL_BACKOFF", "2.0"))
MAX_BACKOFF_SECONDS = float(os.getenv("GROWW_MAX_BACKOFF", "60.0"))

# --- Output paths ---
DATA_DIR = os.getenv("GROWW_DATA_DIR", "data")
RAW_REVIEWS_CSV = os.path.join(DATA_DIR, "raw_reviews.csv")
CLEANED_REVIEWS_CSV = os.path.join(DATA_DIR, "cleaned_reviews.csv")
REVIEWS_FOR_SHEETS_CSV = os.path.join(DATA_DIR, "reviews_for_sheets.csv")
REVIEWS_SAMPLE_CSV = os.path.join(DATA_DIR, "reviews_sample.csv")
ANALYSIS_SAMPLE_CSV = os.path.join(DATA_DIR, "analysis_sample.csv")
SAMPLING_REPORT_JSON = os.path.join(DATA_DIR, "sampling_report.json")
DATA_QUALITY_REPORT_JSON = os.path.join(DATA_DIR, "data_quality_report.json")

# --- Sample size for the commit-safe sample CSV ---
SAMPLE_SIZE = int(os.getenv("GROWW_SAMPLE_SIZE", "50"))

# --- Required CSV columns ---
RAW_COLUMNS = [
    "review_id",
    "review_date",
    "rating",
    "original_review_text",
    "source",
    "source_url",
    "collected_at",
    "app_version",
]

CLEANED_COLUMNS = [
    "review_id",
    "review_date",
    "rating",
    "original_review_text",
    "cleaned_review_text",
    "source",
    "source_url",
    "collected_at",
    "app_version",
    "pii_redacted",
    "exclusion_reason",
    "quote_eligible",
]
