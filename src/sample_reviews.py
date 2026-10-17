"""Reproducible stratified sampling of cleaned Groww reviews.

Selects up to 1,000 reviews from the cleaned dataset using stratified
random sampling across review week and rating. Uses a fixed random seed
(42) for reproducibility. Preserves approximately proportional
representation within each stratum.

Designed to keep Gemini classification costs manageable during prototyping
while maintaining statistical representativeness.
"""

from __future__ import annotations

import csv
import json
import logging
import math
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
for _p in (ROOT, SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import (  # noqa: E402
    ANALYSIS_SAMPLE_CSV,
    CLEANED_REVIEWS_CSV,
    SAMPLING_REPORT_JSON,
    WEEKS_BACK,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("sample_reviews")

RANDOM_SEED = 42
MAX_SAMPLE_SIZE = 1000
SAMPLE_COLUMNS = [
    "review_id",
    "review_date",
    "rating",
    "cleaned_review_text",
    "source",
    "source_url",
    "collected_at",
    "app_version",
    "pii_redacted",
    "quote_eligible",
]


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


def _week_label(review_date: datetime | None, window_start: datetime) -> str:
    """Return a week label (e.g. '2026-W32') for a review date."""
    if review_date is None:
        return "unknown"
    # ISO week of the review date
    iso_year, iso_week, _ = review_date.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def _stratum_key(review_date_label: str, rating: str) -> str:
    """Build a stratum key from week label and rating."""
    return f"{review_date_label}|{rating}"


def load_cleaned_reviews(path: str = CLEANED_REVIEWS_CSV) -> list[dict[str, Any]]:
    """Load cleaned reviews from CSV."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Cleaned reviews CSV not found: {path}")
    rows: list[dict[str, Any]] = []
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    logger.info("Loaded %d cleaned reviews from %s", len(rows), path)
    return rows


def stratified_sample(
    rows: list[dict[str, Any]],
    max_sample_size: int = MAX_SAMPLE_SIZE,
    seed: int = RANDOM_SEED,
    window_start: datetime | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Perform stratified random sampling across week and rating.

    Returns (sample_rows, sampling_report).
    """
    if window_start is None:
        from config import default_window_start

        window_start = default_window_start()

    rng = random.Random(seed)

    # Group rows by stratum (week | rating)
    strata: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        rd = _parse_date(row.get("review_date"))
        week_label = _week_label(rd, window_start)
        rating = row.get("rating", "").strip()
        if rating not in {"1", "2", "3", "4", "5"}:
            rating = "unknown"
        key = _stratum_key(week_label, rating)
        strata[key].append(row)

    logger.info("Identified %d strata (week × rating combinations)", len(strata))

    total_population = len(rows)
    sample_size = min(max_sample_size, total_population)

    # Proportional allocation: largest remainder method
    stratum_counts = {k: len(v) for k, v in strata.items()}
    stratum_sample_targets: dict[str, int] = {}

    if sample_size >= total_population:
        # Take everything
        for k in strata:
            stratum_sample_targets[k] = len(strata[k])
    else:
        # Largest remainder proportional allocation
        exact_allocations = {}
        for k, count in stratum_counts.items():
            exact = count / total_population * sample_size
            exact_allocations[k] = exact
            stratum_sample_targets[k] = int(math.floor(exact))

        allocated = sum(stratum_sample_targets.values())
        remaining = sample_size - allocated

        # Distribute remaining by largest fractional remainder
        remainders = sorted(
            stratum_counts.keys(),
            key=lambda k: exact_allocations[k] - stratum_sample_targets[k],
            reverse=True,
        )
        for i in range(remaining):
            stratum_sample_targets[remainders[i]] += 1

    logger.info(
        "Allocated %d samples across %d strata using largest remainder method",
        sample_size, len(strata),
    )

    # Draw samples from each stratum
    sample_rows: list[dict[str, Any]] = []
    stratum_actual: dict[str, int] = {}
    for key, target in stratum_sample_targets.items():
        pool = strata[key]
        n = min(target, len(pool))
        if n == 0:
            stratum_actual[key] = 0
            continue
        drawn = rng.sample(pool, n)
        sample_rows.extend(drawn)
        stratum_actual[key] = n

    # Sort sample by review_date descending for deterministic output
    sample_rows.sort(
        key=lambda r: r.get("review_date", ""), reverse=True
    )

    # Build sampling report
    pop_rating_dist = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    sample_rating_dist = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
    pop_week_counts: dict[str, int] = defaultdict(int)
    sample_week_counts: dict[str, int] = defaultdict(int)

    for row in rows:
        r = row.get("rating", "").strip()
        if r in pop_rating_dist:
            pop_rating_dist[r] += 1
        rd = _parse_date(row.get("review_date"))
        wl = _week_label(rd, window_start)
        pop_week_counts[wl] += 1

    for row in sample_rows:
        r = row.get("rating", "").strip()
        if r in sample_rating_dist:
            sample_rating_dist[r] += 1
        rd = _parse_date(row.get("review_date"))
        wl = _week_label(rd, window_start)
        sample_week_counts[wl] += 1

    dates = [_parse_date(r.get("review_date")) for r in rows]
    dates = [d for d in dates if d is not None]
    earliest = min(dates).isoformat() if dates else ""
    latest = max(dates).isoformat() if dates else ""

    report = {
        "sampling_method": "stratified_random_sampling",
        "stratification_variables": ["review_week", "rating"],
        "random_seed": seed,
        "max_sample_size": max_sample_size,
        "total_population": total_population,
        "sample_size": len(sample_rows),
        "sampling_fraction": round(len(sample_rows) / total_population, 6)
        if total_population > 0 else 0.0,
        "number_of_strata": len(strata),
        "stratum_allocations": stratum_actual,
        "population_rating_distribution": pop_rating_dist,
        "sample_rating_distribution": sample_rating_dist,
        "population_week_distribution": dict(sorted(pop_week_counts.items())),
        "sample_week_distribution": dict(sorted(sample_week_counts.items())),
        "population_date_range": {
            "earliest": earliest,
            "latest": latest,
        },
        "note": "Sample counts must not be reported as if they represent the whole dataset without applying stratum weights.",
    }

    return sample_rows, report


def write_sample_csv(
    sample_rows: list[dict[str, Any]],
    path: str = ANALYSIS_SAMPLE_CSV,
) -> None:
    """Write the analysis sample to CSV."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SAMPLE_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in sample_rows:
            writer.writerow({k: row.get(k, "") for k in SAMPLE_COLUMNS})
    logger.info("Wrote %d sample rows to %s", len(sample_rows), path)


def write_sampling_report(report: dict[str, Any], path: str = SAMPLING_REPORT_JSON) -> None:
    """Write the sampling report to JSON."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info("Wrote sampling report to %s", path)


def main() -> None:
    rows = load_cleaned_reviews()
    sample_rows, report = stratified_sample(rows)
    write_sample_csv(sample_rows)
    write_sampling_report(report)
    logger.info(
        "Sampling done: %d population → %d sample (seed=%d)",
        report["total_population"], report["sample_size"], RANDOM_SEED,
    )


if __name__ == "__main__":
    main()
