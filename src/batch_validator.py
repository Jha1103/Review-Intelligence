"""Deterministic batch validation for Groww review classification (Phase 3.2).

Python equivalents of the n8n Code node JavaScript validation logic.
Used for local automated testing. The actual n8n Code nodes use JavaScript
(see docs/GEMINI_CLASSIFICATION_PROMPT.md and n8n/phase_3_2_node_instructions.md).
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

# Import taxonomy for valid values
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from taxonomy import (  # noqa: E402
    VALID_FEE_TOPICS,
    VALID_SENTIMENTS,
    VALID_THEME_IDS,
    MAX_THEMES_PER_REVIEW,
)


def validate_batch_classification(
    batch_results: list[dict[str, Any]],
    original_review_ids: list[str],
) -> dict[str, Any]:
    """Validate a single batch's classification results.

    Checks:
    1. Every input review classified exactly once
    2. No unknown or duplicate review IDs
    3. Only valid theme IDs (max 2 per review)
    4. Valid sentiments and fee topics
    5. Correct record counts
    6. Flag questionable fee-subtype claims for manual review

    Returns a dict with:
        valid: bool
        errors: list[str]
        warnings: list[str]
        classified_review_ids: list[str]
    """
    errors: list[str] = []
    warnings: list[str] = []
    classified_ids: list[str] = []

    expected_ids = set(original_review_ids)

    # Check record count matches
    if len(batch_results) != len(expected_ids):
        errors.append(
            f"Record count mismatch: expected {len(expected_ids)} classifications, "
            f"got {len(batch_results)}"
        )

    seen_ids: set[str] = set()

    for i, result in enumerate(batch_results):
        rid = result.get("review_id", "")

        # Check for duplicate review IDs within batch
        if rid in seen_ids:
            errors.append(f"Duplicate review ID in batch results: {rid}")
            continue
        seen_ids.add(rid)

        # Check for unknown review IDs
        if rid not in expected_ids:
            errors.append(f"Unknown review ID in batch results: {rid}")
            continue

        classified_ids.append(rid)

        # Validate themes
        themes = result.get("themes", [])
        if not isinstance(themes, list):
            errors.append(f"Review {rid}: themes is not a list")
            continue
        if len(themes) > MAX_THEMES_PER_REVIEW:
            errors.append(
                f"Review {rid}: {len(themes)} themes assigned, max {MAX_THEMES_PER_REVIEW} allowed"
            )
        invalid_themes = [t for t in themes if t not in VALID_THEME_IDS]
        if invalid_themes:
            errors.append(f"Review {rid}: invalid theme IDs: {invalid_themes}")

        # Validate sentiment
        sentiment = result.get("sentiment", "")
        if sentiment not in VALID_SENTIMENTS:
            errors.append(f"Review {rid}: invalid sentiment '{sentiment}'")

        # Validate fee topic
        fee_topic = result.get("fee_topic", "none")
        if fee_topic not in VALID_FEE_TOPICS:
            errors.append(f"Review {rid}: invalid fee topic '{fee_topic}'")

        # Flag questionable fee-subtype claims for manual review
        if is_fee_questionable(result):
            warnings.append(
                f"Review {rid}: questionable fee-subtype claim, flagged for manual review"
            )

    # Check for missing classifications (reviews not in results)
    missing_ids = expected_ids - seen_ids
    for rid in sorted(missing_ids):
        errors.append(f"Review {rid}: not classified (missing from results)")

    # Check for extra classifications (IDs not in input)
    extra_ids = seen_ids - expected_ids
    for rid in sorted(extra_ids):
        errors.append(f"Review {rid}: classified but not in input batch")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings,
        "classified_review_ids": sorted(classified_ids),
        "missing_review_ids": sorted(missing_ids),
        "extra_review_ids": sorted(extra_ids),
    }


def is_fee_questionable(result: dict[str, Any]) -> bool:
    """Flag reviews where fee-topic claim is questionable for manual review.

    A fee claim is questionable when:
    - themes includes T1 (fees) but fee_topic is 'none'
    - themes does NOT include T1 but fee_topic is 'fee-brokerage' or 'fee-other'
    """
    themes = result.get("themes", [])
    fee_topic = result.get("fee_topic", "none")
    is_fee = "T1" in themes
    has_fee_topic = fee_topic in ("fee-brokerage", "fee-other")
    return is_fee != has_fee_topic


def aggregate_theme_frequencies(
    all_batch_results: list[dict[str, Any]],
    run_label: str = "current_run",
) -> dict[str, Any]:
    """Aggregate theme frequencies across all validated batch results.

    Counts one review at most once per theme (even if a review has 2 themes,
    it contributes 1 to each theme's count).

    Returns a dict with per-theme counts and review counts.
    """
    theme_counts: dict[str, int] = {tid: 0 for tid in VALID_THEME_IDS}
    sentiment_counts: dict[str, int] = {s: 0 for s in VALID_SENTIMENTS}
    fee_topic_counts: dict[str, int] = {ft: 0 for ft in VALID_FEE_TOPICS}
    total_reviews = 0
    reviews_with_themes = 0
    questionable_fees: list[str] = []

    for result in all_batch_results:
        rid = result.get("review_id", "")
        themes = result.get("themes", [])
        sentiment = result.get("sentiment", "")
        fee_topic = result.get("fee_topic", "none")

        total_reviews += 1
        if themes:
            reviews_with_themes += 1
            for tid in themes:
                if tid in theme_counts:
                    theme_counts[tid] += 1

        if sentiment in sentiment_counts:
            sentiment_counts[sentiment] += 1

        if fee_topic in fee_topic_counts:
            fee_topic_counts[fee_topic] += 1

        if is_fee_questionable(result):
            questionable_fees.append(rid)

    return {
        "run_label": run_label,
        "total_reviews_classified": total_reviews,
        "reviews_with_themes": reviews_with_themes,
        "theme_counts": theme_counts,
        "sentiment_counts": sentiment_counts,
        "fee_topic_counts": fee_topic_counts,
        "questionable_fee_review_ids": questionable_fees,
        "questionable_fee_count": len(questionable_fees),
        "scope_labels": {
            "pilot_25_reviews": "separate_pilot_run",
            "initial_test_100_reviews": run_label,
            "full_1000_reviews": "pending_scale_up_approval",
        },
    }


if __name__ == "__main__":
    # Example usage
    sample_results = [
        {"review_id": "r1", "themes": ["T1", "T2"], "sentiment": "negative", "fee_topic": "fee-brokerage"},
        {"review_id": "r2", "themes": ["T5"], "sentiment": "positive", "fee_topic": "none"},
    ]
    original_ids = ["r1", "r2"]
    validation = validate_batch_classification(sample_results, original_ids)
    print(json.dumps(validation, indent=2))

    agg = aggregate_theme_frequencies(sample_results, "test_run")
    print(json.dumps(agg, indent=2))
