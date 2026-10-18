"""Deterministic batch generation for Groww review classification (Phase 3.2).

Generates fixed-size batches of reviews from the 1,000-review stratified sample.
Each batch contains 25 unique reviews with review_id, review_date, rating,
cleaned_review_text, and quote_eligible fields.

Batches are deterministic: same input + same seed = same batches.
No review appears in more than one batch.
Reviews with quote_eligible=no are included but flagged (not eligible for verbatim quotes).

SELECTION METHOD (reproducible, seed-documented):
- Input: 1,000 reviews from the stratified analysis sample
- Sort all reviews by review_id for stable ordering
- Select every 10th review starting from offset = seed % 10
  (seed=42 → offset=2, indices 2, 12, 22, ..., 992)
- This yields exactly 100 reviews spread evenly across the sorted dataset
- Distinct from: the balanced 25-review pilot AND the full 1,000-review sample
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
for _p in (ROOT, SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from config import ANALYSIS_SAMPLE_CSV  # noqa: E402
from taxonomy import BATCH_SIZE, MAX_BATCHES_FOR_INITIAL_TEST, DETERMINISTIC_SEED  # noqa: E402

DEFAULT_SEED = DETERMINISTIC_SEED


def load_sample_reviews(path: str = ANALYSIS_SAMPLE_CSV) -> list[dict[str, Any]]:
    """Load the 1,000-review stratified sample from CSV."""
    if not os.path.exists(path):
        raise FileNotFoundError(f"Analysis sample CSV not found: {path}")
    rows: list[dict[str, Any]] = []
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def deterministic_batch_id(run_id: str, batch_index: int) -> str:
    """Generate a deterministic batch ID from run ID and batch index."""
    h = hashlib.sha256(f"{run_id}:batch:{batch_index}".encode("utf-8")).hexdigest()[:12]
    return f"batch_{batch_index}_{h}"


def select_100_deterministically(
    reviews: list[dict[str, Any]],
    seed: int = DEFAULT_SEED,
) -> list[dict[str, Any]]:
    """Select exactly 100 reviews from 1,000 using deterministic systematic sampling.

    Sort by review_id, then take every 10th review starting from offset = seed % 10.
    This guarantees even coverage across the dataset and full reproducibility.
    """
    if len(reviews) != 1000:
        raise ValueError(
            f"Expected 1000 reviews for deterministic selection, got {len(reviews)}"
        )

    # Sort by review_id for stable ordering
    sorted_reviews = sorted(reviews, key=lambda r: str(r.get("review_id", "")))

    offset = seed % 10
    step = 10  # 1000 / 100 = 10

    selected = []
    for i in range(offset, len(sorted_reviews), step):
        selected.append(sorted_reviews[i])
        if len(selected) >= 100:
            break

    if len(selected) != 100:
        raise ValueError(
            f"Deterministic selection produced {len(selected)} reviews, expected 100"
        )

    return selected


def generate_batches(
    reviews: list[dict[str, Any]],
    batch_size: int = BATCH_SIZE,
    max_batches: int = MAX_BATCHES_FOR_INITIAL_TEST,
    seed: int = DEFAULT_SEED,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Split reviews into deterministic batches.

    First selects 100 reviews deterministically from the 1,000-review sample,
    then splits those 100 into exactly 4 batches of 25.

    No review appears in more than one batch.

    Returns a dict with batch metadata and the list of batches.
    """
    if run_id is None:
        run_id = f"run_{seed}"

    # Step 1: Select 100 reviews deterministically from 1,000
    selected_reviews = select_100_deterministically(reviews, seed=seed)

    # Step 2: Sort selected reviews by review_id for stable batch ordering
    sorted_selected = sorted(
        selected_reviews, key=lambda r: str(r.get("review_id", ""))
    )

    total_selected = len(sorted_selected)
    num_batches = min(max_batches, (total_selected + batch_size - 1) // batch_size)

    batches: list[dict[str, Any]] = []
    for i in range(num_batches):
        start = i * batch_size
        end = min(start + batch_size, total_selected)
        batch_reviews = sorted_selected[start:end]
        batch_id = deterministic_batch_id(run_id, i + 1)
        batches.append(
            {
                "batch_id": batch_id,
                "batch_index": i + 1,
                "run_id": run_id,
                "batch_size": batch_size,
                "review_count": len(batch_reviews),
                "review_ids": [r.get("review_id", "") for r in batch_reviews],
                "reviews": batch_reviews,
                "selection_method": "systematic_step_10_seed_" + str(seed),
                "source_dataset": "analysis_sample_1000",
            }
        )

    # Batch IDs must be unique
    batch_ids = [b["batch_id"] for b in batches]
    assert len(batch_ids) == len(set(batch_ids)), "Duplicate batch IDs generated"

    # No review ID appears in more than one batch
    all_review_ids = [rid for b in batches for rid in b["review_ids"]]
    assert len(all_review_ids) == len(set(all_review_ids)), (
        "Review ID appears in multiple batches"
    )

    # Exactly 100 reviews across 4 batches of 25 (only when max_batches=4)
    total_in_batches = sum(b["review_count"] for b in batches)
    if max_batches >= MAX_BATCHES_FOR_INITIAL_TEST:
        assert total_in_batches == 100, f"Expected 100 reviews, got {total_in_batches}"
        assert num_batches == 4, f"Expected 4 batches, got {num_batches}"

    return {
        "run_id": run_id,
        "seed": seed,
        "selection_method": "systematic_step_10_seed_" + str(seed),
        "source_dataset": "analysis_sample_1000",
        "batch_size": batch_size,
        "max_batches": max_batches,
        "total_reviews_available": 1000,
        "reviews_selected_for_test": 100,
        "num_batches": num_batches,
        "total_reviews_in_batches": total_in_batches,
        "batches": batches,
    }


def write_batches_json(batch_result: dict[str, Any], path: str) -> None:
    """Write batch generation result to JSON file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(batch_result, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    reviews = load_sample_reviews()
    result = generate_batches(reviews)
    print(f"Run ID: {result['run_id']}")
    print(f"Selection method: {result['selection_method']}")
    print(f"Source dataset: {result['source_dataset']}")
    print(f"Total reviews available: {result['total_reviews_available']}")
    print(f"Reviews selected for test: {result['reviews_selected_for_test']}")
    print(f"Number of batches: {result['num_batches']}")
    print(f"Total reviews in batches: {result['total_reviews_in_batches']}")
    for b in result["batches"]:
        print(f"  {b['batch_id']}: {b['review_count']} reviews")
