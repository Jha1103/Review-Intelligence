"""Unit tests using synthetic fixtures only.

Never mixes synthetic test reviews with genuine output data.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
for _p in (ROOT, SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from clean_reviews import (  # noqa: E402
    _is_empty_review,
    _normalize_whitespace,
    _parse_date,
    _redact_pii,
    clean_reviews,
)
from collect_reviews import _fetch_page  # noqa: E402 (test imports only)


# ---------------------------------------------------------------------------
# Synthetic fixtures (never written to genuine data outputs)
# ---------------------------------------------------------------------------

def _make_row(review_id, review_date, rating, text, app_version="1.0.0"):
    return {
        "review_id": review_id,
        "review_date": review_date,
        "rating": str(rating),
        "original_review_text": text,
        "source": "google_play",
        "source_url": "https://play.google.com/store/apps/details?id=com.nextbillion.groww",
        "collected_at": "2026-01-15T10:00:00+00:00",
        "app_version": app_version,
    }


def _write_csv(path, rows, columns):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _run_clean(raw_rows, columns, window_start=None, tmpdir=None):
    """Run clean_reviews with temp output paths to avoid polluting real data."""
    if tmpdir is None:
        tmpdir = tempfile.mkdtemp()
    raw_path = os.path.join(tmpdir, "raw.csv")
    cleaned_path = os.path.join(tmpdir, "cleaned.csv")
    sample_path = os.path.join(tmpdir, "sample.csv")
    report_path = os.path.join(tmpdir, "report.json")
    exclusion_path = os.path.join(tmpdir, "exclusions.log")
    _write_csv(raw_path, raw_rows, columns)
    result = clean_reviews(
        raw_path=raw_path,
        window_start=window_start,
        cleaned_path=cleaned_path,
        sample_path=sample_path,
        report_path=report_path,
        exclusion_path=exclusion_path,
    )
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_date_window_filtering():
    """Reviews inside the 12-week window are kept; older ones are dropped."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(weeks=12)
    inside = (now - timedelta(weeks=6)).isoformat()
    outside = (now - timedelta(weeks=20)).isoformat()

    rows = [
        _make_row("r1", inside, 5, "Great app"),
        _make_row("r2", outside, 1, "Old review"),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        raw_path = os.path.join(tmp, "raw.csv")
        _write_csv(raw_path, rows, list(rows[0].keys()))
        result = _run_clean(rows, list(rows[0].keys()), window_start=window_start, tmpdir=tmp)

    ids = {r["review_id"] for r in result["cleaned_rows"]}
    assert "r1" in ids
    assert "r2" not in ids


def test_original_id_preservation():
    """Original review IDs are preserved exactly through cleaning."""
    now = datetime.now(timezone.utc).isoformat()
    rows = [_make_row("gp_abc123xyz", now, 4, "Good app")]

    with tempfile.TemporaryDirectory() as tmp:
        raw_path = os.path.join(tmp, "raw.csv")
        _write_csv(raw_path, rows, list(rows[0].keys()))
        result = _run_clean(rows, list(rows[0].keys()), tmpdir=tmp)

    assert len(result["cleaned_rows"]) == 1
    assert result["cleaned_rows"][0]["review_id"] == "gp_abc123xyz"


def test_duplicate_removal():
    """Duplicate review IDs are removed; first occurrence is preserved."""
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        _make_row("dup_1", now, 5, "First occurrence"),
        _make_row("dup_1", now, 1, "Duplicate"),
        _make_row("dup_2", now, 4, "Unique"),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        raw_path = os.path.join(tmp, "raw.csv")
        _write_csv(raw_path, rows, list(rows[0].keys()))
        result = _run_clean(rows, list(rows[0].keys()), tmpdir=tmp)

    ids = [r["review_id"] for r in result["cleaned_rows"]]
    assert ids.count("dup_1") == 1
    assert "dup_2" in ids
    assert result["quality_report"]["duplicate_reviews_removed"] >= 1


def test_rating_mapping():
    """Ratings are preserved as integers 1-5."""
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        _make_row("r1", now, 1, "Bad"),
        _make_row("r2", now, 3, "OK"),
        _make_row("r3", now, 5, "Excellent"),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        raw_path = os.path.join(tmp, "raw.csv")
        _write_csv(raw_path, rows, list(rows[0].keys()))
        result = _run_clean(rows, list(rows[0].keys()), tmpdir=tmp)

    ratings = sorted(int(r["rating"]) for r in result["cleaned_rows"])
    assert ratings == [1, 3, 5]


def test_text_preservation():
    """Original review text is preserved exactly in original_review_text."""
    now = datetime.now(timezone.utc).isoformat()
    original = "The app crashes every time I open it on my Pixel 7!"
    rows = [_make_row("r1", now, 2, original)]

    with tempfile.TemporaryDirectory() as tmp:
        raw_path = os.path.join(tmp, "raw.csv")
        _write_csv(raw_path, rows, list(rows[0].keys()))
        result = _run_clean(rows, list(rows[0].keys()), tmpdir=tmp)

    assert result["cleaned_rows"][0]["original_review_text"] == original


def test_pii_redaction_email():
    """Email addresses are redacted in cleaned_review_text."""
    text = "Contact me at user@example.com for details"
    redacted, was_redacted = _redact_pii(text)
    assert was_redacted is True
    assert "user@example.com" not in redacted
    assert "[REDACTED]" in redacted


def test_pii_redaction_phone():
    """Indian phone numbers are redacted in cleaned_review_text."""
    text = "Call me at 9876543210"
    redacted, was_redacted = _redact_pii(text)
    assert was_redacted is True
    assert "9876543210" not in redacted
    assert "[REDACTED]" in redacted


def test_pii_redaction_pan():
    """PAN-like patterns are redacted."""
    text = "PAN: ABCDE1234F"
    redacted, was_redacted = _redact_pii(text)
    assert was_redacted is True
    assert "ABCDE1234F" not in redacted


def test_pii_no_false_positive_on_clean_text():
    """Normal review text without PII is not redacted."""
    text = "The app is very slow and frustrating"
    redacted, was_redacted = _redact_pii(text)
    assert was_redacted is False
    assert redacted == text


def test_empty_review_handling():
    """Empty or whitespace-only reviews are removed."""
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        _make_row("r1", now, 5, ""),
        _make_row("r2", now, 4, "   "),
        _make_row("r3", now, 3, "Valid short complaint"),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        raw_path = os.path.join(tmp, "raw.csv")
        _write_csv(raw_path, rows, list(rows[0].keys()))
        result = _run_clean(rows, list(rows[0].keys()), tmpdir=tmp)

    ids = {r["review_id"] for r in result["cleaned_rows"]}
    assert "r1" not in ids
    assert "r2" not in ids
    assert "r3" in ids


def test_short_reviews_not_removed_automatically():
    """Short fee-related complaints are preserved."""
    now = datetime.now(timezone.utc).isoformat()
    rows = [_make_row("r1", now, 1, "Charged twice")]

    with tempfile.TemporaryDirectory() as tmp:
        raw_path = os.path.join(tmp, "raw.csv")
        _write_csv(raw_path, rows, list(rows[0].keys()))
        result = _run_clean(rows, list(rows[0].keys()), tmpdir=tmp)

    assert len(result["cleaned_rows"]) == 1
    assert result["cleaned_rows"][0]["cleaned_review_text"] == "Charged twice"


def test_dataset_schema():
    """Cleaned CSV contains all required columns."""
    now = datetime.now(timezone.utc).isoformat()
    rows = [_make_row("r1", now, 5, "Fine")]

    with tempfile.TemporaryDirectory() as tmp:
        raw_path = os.path.join(tmp, "raw.csv")
        _write_csv(raw_path, rows, list(rows[0].keys()))
        result = _run_clean(rows, list(rows[0].keys()), tmpdir=tmp)

    # Verify schema from the cleaned_rows returned by the pipeline
    columns = list(result["cleaned_rows"][0].keys()) if result["cleaned_rows"] else []
    for required in [
        "review_id", "review_date", "rating", "original_review_text",
        "cleaned_review_text", "source", "source_url", "collected_at",
        "app_version", "pii_redacted",
    ]:
        assert required in columns, f"Missing column: {required}"


def test_quality_report_consistency():
    """Quality report counts are consistent with cleaned output."""
    now = datetime.now(timezone.utc).isoformat()
    rows = [
        _make_row("r1", now, 5, "Good"),
        _make_row("r2", now, 4, "OK"),
        _make_row("r3", now, 3, "Fine"),
    ]

    with tempfile.TemporaryDirectory() as tmp:
        raw_path = os.path.join(tmp, "raw.csv")
        _write_csv(raw_path, rows, list(rows[0].keys()))
        result = _run_clean(rows, list(rows[0].keys()), tmpdir=tmp)

    report = result["quality_report"]
    assert report["final_cleaned_reviews"] == len(result["cleaned_rows"])
    assert report["final_cleaned_reviews"] == 3
    assert sum(report["rating_distribution"].values()) == 3
    assert report["earliest_eligible_review_date"] != ""
    assert report["latest_eligible_review_date"] != ""


def test_whitespace_normalization():
    """Extra whitespace is collapsed in cleaned text."""
    text = "The   app   is    slow"
    normalized = _normalize_whitespace(text)
    assert normalized == "The app is slow"
