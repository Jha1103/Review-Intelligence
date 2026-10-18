"""Deterministic batch validation for Groww review classification (Phase 3.2).

Python equivalents of the n8n Code node JavaScript validation logic.
Used for local automated testing. The actual n8n Code nodes use JavaScript
(see docs/GEMINI_CLASSIFICATION_PROMPT.md and n8n/phase_3_2_node_instructions.md).

Key rules:
- Exactly 25 classifications per batch, all expected review IDs present once
- No duplicates, no invented IDs
- Valid theme IDs (max 2 per review, empty array allowed for unclassified)
- Valid sentiments: positive, negative, neutral, unclear, mixed
- Valid fee topics: brokerage, dp_charges, other_fee, unspecified_fee, none, unclear
- Fee-topic consistency: T1 assigned ⟺ fee_topic is a specific fee subtype
- Flag questionable fee-subtype claims and ambiguous classifications for manual review
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
    is_fee_questionable,
)

# Expected batch size
EXPECTED_BATCH_SIZE = 25


def parse_gemini_response_text(raw_text: str) -> list[dict[str, Any]]:
    """Safely parse Gemini response text containing JSON array.

    Gemini returns classifications in content.parts[0].text as a JSON string.
    This function parses that string and returns a list of classification objects.
    """
    if not raw_text or not isinstance(raw_text, str):
        raise ValueError("Gemini response text is empty or not a string")

    text = raw_text.strip()

    # Try to find JSON array within the text (handle markdown fences, extra text)
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON array found in Gemini response text")

    json_str = text[start : end + 1]
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse Gemini response JSON: {e}")

    if not isinstance(parsed, list):
        raise ValueError("Gemini response is not a JSON array")

    return parsed


def validate_batch_classification(
    batch_results: list[dict[str, Any]],
    original_review_ids: list[str],
) -> dict[str, Any]:
    """Validate a single batch's classification results.

    Checks:
    1. Exactly 25 classifications (matching input review count)
    2. Every input review classified exactly once
    3. No unknown or duplicate review IDs
    4. Only valid theme IDs (max 2 per review, empty array allowed)
    5. Valid sentiments (positive, negative, neutral, unclear, mixed)
    6. Valid fee topics (brokerage, dp_charges, other_fee, unspecified_fee, none, unclear)
    7. Fee-topic consistency with themes
    8. Flag questionable fee-subtype claims for manual review

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
    expected_count = len(expected_ids)

    # Check record count matches exactly 25
    if len(batch_results) != expected_count:
        errors.append(
            f"Record count mismatch: expected {expected_count} classifications, "
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

        # Validate themes (empty array allowed for unclassified)
        themes = result.get("themes", [])
        if not isinstance(themes, list):
            errors.append(f"Review {rid}: themes is not a list")
            continue
        if len(themes) > MAX_THEMES_PER_REVIEW:
            errors.append(
                f"Review {rid}: {len(themes)} themes assigned, "
                f"max {MAX_THEMES_PER_REVIEW} allowed"
            )
        invalid_themes = [t for t in themes if t not in VALID_THEME_IDS]
        if invalid_themes:
            errors.append(f"Review {rid}: invalid theme IDs: {invalid_themes}")

        # Validate sentiment (includes unclear, mixed)
        sentiment = result.get("sentiment", "")
        if sentiment not in VALID_SENTIMENTS:
            errors.append(f"Review {rid}: invalid sentiment '{sentiment}'")

        # Validate fee topic
        fee_topic = result.get("fee_topic", "none")
        if fee_topic not in VALID_FEE_TOPICS:
            errors.append(f"Review {rid}: invalid fee topic '{fee_topic}'")

        # Fee-topic consistency check
        if is_fee_questionable(result):
            warnings.append(
                f"Review {rid}: questionable fee-subtype claim "
                f"(T1={'T1' in themes}, fee_topic={fee_topic}), "
                f"flagged for manual review"
            )

        # Flag ambiguous classifications for manual review
        if result.get("needs_manual_review", False):
            warnings.append(
                f"Review {rid}: marked needs_manual_review by model"
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
        "classified_count": len(classified_ids),
        "input_count": expected_count,
    }


def extract_classifications_from_gemini_response(
    gemini_output: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extract classification array from Gemini node output.

    The Gemini node returns the response in content.parts[0].text as a JSON string.
    This function navigates that structure and parses the JSON array.

    Expected structure:
        {
          "content": {
            "parts": [
              {
                "text": "[{\"review_id\": \"...\", \"themes\": [...], ...}]"
              }
            ]
          }
        }

    Returns a list of classification objects.
    """
    if not isinstance(gemini_output, dict):
        raise ValueError("Gemini output is not a dictionary")

    content = gemini_output.get("content")
    if not isinstance(content, dict):
        raise ValueError("Gemini output missing 'content' field")

    parts = content.get("parts")
    if not isinstance(parts, list) or len(parts) == 0:
        raise ValueError("Gemini output missing 'content.parts' array")

    part_text = parts[0].get("text", "") if isinstance(parts[0], dict) else ""
    if not part_text:
        raise ValueError("Gemini output missing 'content.parts[0].text'")

    return parse_gemini_response_text(part_text)


def aggregate_theme_frequencies(
    all_batch_results: list[dict[str, Any]],
    run_label: str = "phase_3_2_initial_test",
    require_full_count: bool = True,
) -> dict[str, Any]:
    """Aggregate theme frequencies across all validated batch results.

    Counts one review at most once per theme (even if a review has 2 themes,
    it contributes 1 to each theme's count).

    When require_full_count=True (default for production n8n use), requires
    exactly 100 unique classified reviews across 4 batches and fails if any
    batch is missing, failed, duplicated, or unverified.

    When require_full_count=False (for testing with fewer reviews), skips
    the count requirement but still aggregates what is provided.

    Returns a dict with per-theme counts and review counts.
    """
    theme_counts: dict[str, int] = {tid: 0 for tid in VALID_THEME_IDS}
    sentiment_counts: dict[str, int] = {s: 0 for s in VALID_SENTIMENTS}
    fee_topic_counts: dict[str, int] = {ft: 0 for ft in VALID_FEE_TOPICS}
    total_reviews = 0
    reviews_with_themes = 0
    reviews_without_themes = 0
    questionable_fees: list[str] = []
    manual_review_flags: list[str] = []
    all_classified_ids: list[str] = []

    for result in all_batch_results:
        rid = result.get("review_id", "")
        themes = result.get("themes", [])
        sentiment = result.get("sentiment", "")
        fee_topic = result.get("fee_topic", "none")

        total_reviews += 1
        all_classified_ids.append(rid)

        if themes:
            reviews_with_themes += 1
            for tid in themes:
                if tid in theme_counts:
                    theme_counts[tid] += 1
        else:
            reviews_without_themes += 1

        if sentiment in sentiment_counts:
            sentiment_counts[sentiment] += 1

        if fee_topic in fee_topic_counts:
            fee_topic_counts[fee_topic] += 1

        if is_fee_questionable(result):
            questionable_fees.append(rid)

        if result.get("needs_manual_review", False):
            manual_review_flags.append(rid)

    # Require exactly 100 unique classified reviews (production mode only)
    unique_ids = set(all_classified_ids)
    if require_full_count:
        if len(unique_ids) != 100:
            raise ValueError(
                f"Aggregation failed: expected 100 unique classified reviews, "
                f"got {len(unique_ids)}"
            )
        if len(all_classified_ids) != len(unique_ids):
            raise ValueError(
                "Aggregation failed: duplicate review IDs found across batches"
            )

    return {
        "run_label": run_label,
        "total_reviews_classified": total_reviews,
        "unique_reviews_classified": len(unique_ids),
        "reviews_with_themes": reviews_with_themes,
        "reviews_without_themes": reviews_without_themes,
        "theme_counts": theme_counts,
        "sentiment_counts": sentiment_counts,
        "fee_topic_counts": fee_topic_counts,
        "questionable_fee_review_ids": questionable_fees,
        "questionable_fee_count": len(questionable_fees),
        "manual_review_review_ids": manual_review_flags,
        "manual_review_count": len(manual_review_flags),
        "all_classified_review_ids": sorted(all_classified_ids),
        "classification_complete": total_reviews == 100 and len(unique_ids) == 100,
        "aggregated_at": __import__("datetime").datetime.now().isoformat(),
        "scope_labels": {
            "pilot_25_reviews": "separate_pilot_run",
            "initial_test_100_reviews": run_label,
            "full_1000_reviews": "pending_scale_up_approval",
        },
    }


if __name__ == "__main__":
    # Example usage
    sample_results = [
        {"review_id": "r1", "themes": ["T1", "T2"], "sentiment": "negative",
         "fee_topic": "brokerage", "needs_manual_review": False},
        {"review_id": "r2", "themes": [], "sentiment": "unclear",
         "fee_topic": "none", "needs_manual_review": True},
    ]
    original_ids = ["r1", "r2"]
    validation = validate_batch_classification(sample_results, original_ids)
    print(json.dumps(validation, indent=2))
