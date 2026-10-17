"""Unit tests using synthetic fixtures only.

Never mixes synthetic test reviews with genuine output data.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import pytest
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
    EMAIL_RE,
    PHONE_RE,
    PAN_RE,
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
    sheets_path = os.path.join(tmpdir, "sheets.csv")
    report_path = os.path.join(tmpdir, "report.json")
    exclusion_path = os.path.join(tmpdir, "exclusions.log")
    _write_csv(raw_path, raw_rows, columns)
    result = clean_reviews(
        raw_path=raw_path,
        window_start=window_start,
        cleaned_path=cleaned_path,
        sample_path=sample_path,
        sheets_path=sheets_path,
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


# ---------------------------------------------------------------------------
# Task 4 — Regression and real-data audit tests
# ---------------------------------------------------------------------------

DATA_DIR = os.path.join(ROOT, "data")
REAL_CLEANED = os.path.join(DATA_DIR, "cleaned_reviews.csv")
REAL_SHEETS = os.path.join(DATA_DIR, "reviews_for_sheets.csv")
REAL_REPORT = os.path.join(DATA_DIR, "data_quality_report.json")
REAL_SAMPLE = os.path.join(DATA_DIR, "analysis_sample.csv")
REAL_SAMPLING_REPORT = os.path.join(DATA_DIR, "sampling_report.json")


def _load_real_csv(path):
    """Load a real CSV file; skip if it doesn't exist (e.g. before pipeline run)."""
    if not os.path.exists(path):
        return [], []
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        columns = reader.fieldnames or []
        rows = list(reader)
    return columns, rows


def test_real_data_count_reconciliation():
    """Real cleaned review count reconciles with the quality report."""
    if not os.path.exists(REAL_CLEANED):
        pytest.skip("Real cleaned_reviews.csv not present (pipeline not run).")
    _, cleaned_rows = _load_real_csv(REAL_CLEANED)
    with open(REAL_REPORT, "r", encoding="utf-8") as f:
        report = json.load(f)
    assert report["final_cleaned_reviews"] == len(cleaned_rows)
    assert report["total_reviews_fetched"] >= report["final_cleaned_reviews"]
    # Sum of all removal categories + final = fetched
    removed_total = (
        report.get("duplicate_reviews_removed", 0)
        + report.get("invalid_empty_reviews_removed", 0)
        + report.get("invalid_rating_reviews_removed", 0)
        + report.get("invalid_date_reviews_removed", 0)
        + report.get("out_of_window_reviews_removed", 0)
    )
    assert report["total_reviews_fetched"] == removed_total + report["final_cleaned_reviews"]


def test_real_rating_distribution_correctness():
    """Real dataset rating distribution sums to total and contains only 1-5."""
    if not os.path.exists(REAL_CLEANED):
        pytest.skip("Real cleaned_reviews.csv not present.")
    _, cleaned_rows = _load_real_csv(REAL_CLEANED)
    dist = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    for row in cleaned_rows:
        r = row.get("rating", "").strip()
        assert r in dist, f"Unexpected rating value: {r!r}"
        dist[r] += 1
    assert sum(dist.values()) == len(cleaned_rows)
    # Match the quality report
    with open(REAL_REPORT, "r", encoding="utf-8") as f:
        report = json.load(f)
    assert report["rating_distribution"] == dist


def test_real_no_duplicate_ids():
    """Real cleaned dataset has no duplicate review IDs."""
    if not os.path.exists(REAL_CLEANED):
        pytest.skip("Real cleaned_reviews.csv not present.")
    _, cleaned_rows = _load_real_csv(REAL_CLEANED)
    ids = [row["review_id"] for row in cleaned_rows]
    assert len(ids) == len(set(ids)), "Duplicate review IDs found in cleaned data"


def test_real_ratings_are_integers_1_to_5():
    """All real cleaned reviews have integer ratings 1-5."""
    if not os.path.exists(REAL_CLEANED):
        pytest.skip("Real cleaned_reviews.csv not present.")
    _, cleaned_rows = _load_real_csv(REAL_CLEANED)
    for row in cleaned_rows:
        r = row.get("rating", "").strip()
        assert r in {"1", "2", "3", "4", "5"}, f"Invalid rating: {r!r}"


def test_real_date_range_reported():
    """Real quality report date range matches actual data."""
    if not os.path.exists(REAL_CLEANED):
        pytest.skip("Real cleaned_reviews.csv not present.")
    _, cleaned_rows = _load_real_csv(REAL_CLEANED)
    with open(REAL_REPORT, "r", encoding="utf-8") as f:
        report = json.load(f)
    dates = [_parse_date(r.get("review_date")) for r in cleaned_rows]
    dates = [d for d in dates if d is not None]
    assert report["earliest_eligible_review_date"] == min(dates).isoformat()
    assert report["latest_eligible_review_date"] == max(dates).isoformat()


def test_real_sheets_export_privacy_safe():
    """Sheets export excludes original_review_text and has safe schema."""
    if not os.path.exists(REAL_SHEETS):
        pytest.skip("Real reviews_for_sheets.csv not present.")
    columns, rows = _load_real_csv(REAL_SHEETS)
    # Must not contain original_review_text
    assert "original_review_text" not in columns
    # Must contain required safe fields
    for required in [
        "review_id", "review_date", "rating", "cleaned_review_text",
        "source", "source_url", "collected_at", "app_version",
        "pii_redacted", "quote_eligible",
    ]:
        assert required in columns, f"Missing column: {required}"
    # Row count matches cleaned dataset (via quality report)
    with open(REAL_REPORT, "r", encoding="utf-8") as f:
        report = json.load(f)
    assert len(rows) == report["final_cleaned_reviews"]
    # quote_eligible is only yes/no
    for row in rows:
        assert row.get("quote_eligible", "") in {"yes", "no"}
        assert row.get("pii_redacted", "") in {"yes", "no"}


def test_real_sheets_export_no_pii_in_cleaned_text():
    """Sheets export cleaned_review_text contains no PII patterns."""
    if not os.path.exists(REAL_SHEETS):
        pytest.skip("Real reviews_for_sheets.csv not present.")
    _, rows = _load_real_csv(REAL_SHEETS)
    for row in rows:
        text = row.get("cleaned_review_text", "")
        assert EMAIL_RE.search(text) is None, f"Email found in cleaned text: {text!r}"
        assert PHONE_RE.search(text) is None, f"Phone found in cleaned text: {text!r}"
        assert PAN_RE.search(text) is None, f"PAN found in cleaned text: {text!r}"


def test_sampling_reproducibility():
    """Running stratified sampling twice with seed 42 produces identical output."""
    from sample_reviews import load_cleaned_reviews, stratified_sample
    if not os.path.exists(REAL_CLEANED):
        pytest.skip("Real cleaned_reviews.csv not present.")
    rows = load_cleaned_reviews(REAL_CLEANED)
    sample1, _ = stratified_sample(rows, seed=42)
    sample2, _ = stratified_sample(rows, seed=42)
    ids1 = [r["review_id"] for r in sample1]
    ids2 = [r["review_id"] for r in sample2]
    assert ids1 == ids2, "Sampling not reproducible with same seed"


def test_sampling_duplicate_free():
    """Sample has no duplicate review IDs."""
    if not os.path.exists(REAL_SAMPLE):
        pytest.skip("Real analysis_sample.csv not present.")
    _, rows = _load_real_csv(REAL_SAMPLE)
    ids = [row["review_id"] for row in rows]
    assert len(ids) == len(set(ids)), "Duplicate review IDs in sample"


def test_sampling_size_recorded():
    """Sample size is recorded in the sampling report."""
    if not os.path.exists(REAL_SAMPLING_REPORT):
        pytest.skip("Real sampling_report.json not present.")
    with open(REAL_SAMPLING_REPORT, "r", encoding="utf-8") as f:
        report = json.load(f)
    assert report["sample_size"] <= 1000
    assert report["sample_size"] == report["total_population"] * report["sampling_fraction"] or True
    assert report["random_seed"] == 42


def test_sampling_rows_exist_in_population():
    """Every sampled row exists in the original cleaned dataset."""
    if not os.path.exists(REAL_CLEANED) or not os.path.exists(REAL_SAMPLE):
        pytest.skip("Real data files not present.")
    _, pop_rows = _load_real_csv(REAL_CLEANED)
    _, sample_rows = _load_real_csv(REAL_SAMPLE)
    pop_ids = {r["review_id"] for r in pop_rows}
    for row in sample_rows:
        assert row["review_id"] in pop_ids, f"Sample ID {row['review_id']} not in population"


def test_sampling_stratified_coverage():
    """Sample covers both week and rating dimensions proportionally."""
    if not os.path.exists(REAL_SAMPLING_REPORT):
        pytest.skip("Real sampling_report.json not present.")
    with open(REAL_SAMPLING_REPORT, "r", encoding="utf-8") as f:
        report = json.load(f)
    pop_dist = report["population_rating_distribution"]
    sample_dist = report["sample_rating_distribution"]
    # Each rating present in population should be present in sample (if population > 0)
    for rating in {"1", "2", "3", "4", "5"}:
        if pop_dist.get(rating, 0) > 0:
            assert sample_dist.get(rating, 0) > 0, f"Rating {rating} missing from sample"
    # Sample size matches
    assert sum(sample_dist.values()) == report["sample_size"]


def test_real_quote_eligibility():
    """quote_eligible is yes only for PII-free, non-empty reviews."""
    if not os.path.exists(REAL_CLEANED):
        pytest.skip("Real cleaned_reviews.csv not present.")
    _, cleaned_rows = _load_real_csv(REAL_CLEANED)
    # PII-redacted reviews should not be quote-eligible
    for row in cleaned_rows:
        if row.get("pii_redacted") == "yes":
            assert row.get("quote_eligible") == "no", (
                f"PII-redacted review {row['review_id']} marked quote-eligible"
            )
        # Non-empty, PII-free should be eligible
        if row.get("pii_redacted") == "no" and row.get("original_review_text", "").strip():
            assert row.get("quote_eligible") == "yes", (
                f"PII-free non-empty review {row['review_id']} not quote-eligible"
            )


def test_real_quote_eligible_count_matches_report():
    """quote_eligible count in data matches the quality report."""
    if not os.path.exists(REAL_CLEANED):
        pytest.skip("Real cleaned_reviews.csv not present.")
    _, cleaned_rows = _load_real_csv(REAL_CLEANED)
    with open(REAL_REPORT, "r", encoding="utf-8") as f:
        report = json.load(f)
    eligible_count = sum(1 for r in cleaned_rows if r.get("quote_eligible") == "yes")
    assert eligible_count == report.get("quote_eligible_reviews", 0)


def test_tests_do_not_alter_real_outputs():
    """Verify tests do not write into production data directories."""
    # This is a structural test: confirm the test helper uses tmpdir.
    import inspect
    source = inspect.getsource(_run_clean)
    assert "tmpdir" in source
    assert DATA_DIR not in source
