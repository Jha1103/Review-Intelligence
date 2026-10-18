"""Automated tests for Phase 3.2 — Review Classification (synthetic fixtures only).

Tests taxonomy, batch generation, validation, and aggregation logic using
synthetic fixtures. Never mixes synthetic test reviews with genuine output data.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
for _p in (ROOT, SRC):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from taxonomy import (  # noqa: E402
    THEME_TAXONOMY,
    VALID_FEE_TOPICS,
    VALID_SENTIMENTS,
    VALID_THEME_IDS,
    MAX_THEMES_PER_REVIEW,
    BATCH_SIZE,
    MAX_BATCHES_FOR_INITIAL_TEST,
    get_theme_name,
    validate_theme_ids,
    validate_sentiment,
    validate_fee_topic,
    is_fee_related,
    get_taxonomy_json,
)
from batch_generator import (  # noqa: E402
    load_sample_reviews,
    deterministic_batch_id,
    generate_batches,
)
from batch_validator import (  # noqa: E402
    validate_batch_classification,
    is_fee_questionable,
    aggregate_theme_frequencies,
)


# ---------------------------------------------------------------------------
# Synthetic fixtures (never written to genuine data outputs)
# ---------------------------------------------------------------------------

def _make_review(review_id, review_date="2026-10-15", rating=5,
                 text="Good app", source="google_play",
                 source_url="https://play.google.com/store/apps/details?id=com.nextbillion.groww",
                 collected_at="2026-10-15T10:00:00+00:00",
                 app_version="18.0.0", pii_redacted="no", quote_eligible="yes"):
    return {
        "review_id": review_id,
        "review_date": review_date,
        "rating": str(rating),
        "cleaned_review_text": text,
        "source": source,
        "source_url": source_url,
        "collected_at": collected_at,
        "app_version": app_version,
        "pii_redacted": pii_redacted,
        "quote_eligible": quote_eligible,
    }


def _make_classification(review_id, themes=["T5"], sentiment="positive",
                          fee_topic="none", needs_manual_review=False,
                          reasoning="Test review"):
    return {
        "review_id": review_id,
        "themes": themes,
        "sentiment": sentiment,
        "fee_topic": fee_topic,
        "needs_manual_review": needs_manual_review,
        "reasoning": reasoning,
    }


# ---------------------------------------------------------------------------
# Taxonomy tests
# ---------------------------------------------------------------------------

def test_taxonomy_has_exactly_5_themes():
    """Taxonomy contains at most 5 themes."""
    assert len(THEME_TAXONOMY) == 5
    assert set(THEME_TAXONOMY.keys()) == {"T1", "T2", "T3", "T4", "T5"}


def test_taxonomy_theme_structure():
    """Each theme has required fields."""
    for tid, theme in THEME_TAXONOMY.items():
        assert "name" in theme
        assert "description" in theme
        assert "assignment_criteria" in theme
        assert "examples" in theme
        assert "counter_examples" in theme
        assert isinstance(theme["examples"], list)
        assert isinstance(theme["counter_examples"], list)
        assert len(theme["name"]) > 0
        assert len(theme["description"]) > 0


def test_get_theme_name():
    """Theme name lookup works."""
    assert get_theme_name("T1") == "High Fees"
    assert get_theme_name("T5") == "General Satisfaction"
    assert get_theme_name("T99") == "Unknown"


def test_validate_theme_ids():
    """Theme ID validation."""
    assert validate_theme_ids(["T1", "T2"]) is True
    assert validate_theme_ids(["T99"]) is False
    assert validate_theme_ids(["T1", "T99"]) is False
    assert validate_theme_ids("T1") is False  # not a list


def test_validate_sentiment():
    """Sentiment validation."""
    for s in VALID_SENTIMENTS:
        assert validate_sentiment(s) is True
    assert validate_sentiment("happy") is False
    assert validate_sentiment("") is False


def test_validate_fee_topic():
    """Fee topic validation."""
    for ft in VALID_FEE_TOPICS:
        assert validate_fee_topic(ft) is True
    assert validate_fee_topic("brokerage_only") is False


def test_is_fee_related():
    """Fee-related theme detection."""
    assert is_fee_related(["T1"]) is True
    assert is_fee_related(["T1", "T2"]) is True
    assert is_fee_related(["T2"]) is False
    assert is_fee_related(["T5"]) is False


def test_max_themes_per_review():
    """Maximum 2 themes per review enforced."""
    assert MAX_THEMES_PER_REVIEW == 2


# ---------------------------------------------------------------------------
# Batch generation tests
# ---------------------------------------------------------------------------

def test_generate_batches_deterministic():
    """Same input produces same batches."""
    reviews = [
        _make_review(f"r{i:04d}", rating=(i % 5) + 1)
        for i in range(100)
    ]
    result1 = generate_batches(reviews, seed=42, run_id="run_a")
    result2 = generate_batches(reviews, seed=42, run_id="run_a")
    assert result1["run_id"] == result2["run_id"]
    assert result1["num_batches"] == result2["num_batches"]
    for b1, b2 in zip(result1["batches"], result2["batches"]):
        assert b1["batch_id"] == b2["batch_id"]
        assert b1["review_ids"] == b2["review_ids"]


def test_generate_batches_no_duplicates():
    """No review appears in more than one batch."""
    reviews = [_make_review(f"r{i:04d}") for i in range(100)]
    result = generate_batches(reviews)
    all_ids = [rid for b in result["batches"] for rid in b["review_ids"]]
    assert len(all_ids) == len(set(all_ids)), "Review ID appears in multiple batches"


def test_generate_batches_all_reviews_covered():
    """All input reviews appear in exactly one batch."""
    reviews = [_make_review(f"r{i:04d}") for i in range(100)]
    result = generate_batches(reviews, max_batches=10)
    all_ids = [rid for b in result["batches"] for rid in b["review_ids"]]
    input_ids = [r["review_id"] for r in reviews]
    assert sorted(all_ids) == sorted(input_ids)


def test_generate_batches_batch_size():
    """Each batch has at most BATCH_SIZE reviews."""
    reviews = [_make_review(f"r{i:04d}") for i in range(100)]
    result = generate_batches(reviews, max_batches=10)
    for b in result["batches"]:
        assert b["review_count"] <= BATCH_SIZE


def test_generate_batches_max_batches_for_test():
    """Initial test limited to MAX_BATCHES_FOR_INITIAL_TEST batches."""
    reviews = [_make_review(f"r{i:04d}") for i in range(1000)]
    result = generate_batches(reviews)
    assert result["num_batches"] == MAX_BATCHES_FOR_INITIAL_TEST
    assert result["total_reviews_in_batches"] == MAX_BATCHES_FOR_INITIAL_TEST * BATCH_SIZE


def test_deterministic_batch_id():
    """Batch IDs are deterministic."""
    bid1 = deterministic_batch_id("run_1", 1)
    bid2 = deterministic_batch_id("run_1", 1)
    bid3 = deterministic_batch_id("run_2", 1)
    assert bid1 == bid2
    assert bid1 != bid3


def test_batch_ids_unique():
    """Generated batch IDs are unique."""
    reviews = [_make_review(f"r{i:04d}") for i in range(100)]
    result = generate_batches(reviews)
    batch_ids = [b["batch_id"] for b in result["batches"]]
    assert len(batch_ids) == len(set(batch_ids))


# ---------------------------------------------------------------------------
# Batch validation tests
# ---------------------------------------------------------------------------

def test_validate_batch_all_valid():
    """Valid batch classification passes validation."""
    reviews = [_make_review(f"r{i:04d}") for i in range(3)]
    results = [
        _make_classification("r0000", themes=["T1"], sentiment="negative", fee_topic="fee-brokerage"),
        _make_classification("r0001", themes=["T5"], sentiment="positive", fee_topic="none"),
        _make_classification("r0002", themes=["T2", "T3"], sentiment="negative", fee_topic="none"),
    ]
    original_ids = [r["review_id"] for r in reviews]
    validation = validate_batch_classification(results, original_ids)
    assert validation["valid"] is True
    assert validation["errors"] == []
    assert len(validation["classified_review_ids"]) == 3


def test_validate_batch_missing_review():
    """Missing classification is detected."""
    reviews = [_make_review(f"r{i:04d}") for i in range(3)]
    results = [
        _make_classification("r0000", themes=["T1"]),
        _make_classification("r0001", themes=["T5"]),
        # r0002 missing
    ]
    original_ids = [r["review_id"] for r in reviews]
    validation = validate_batch_classification(results, original_ids)
    assert validation["valid"] is False
    assert "r0002" in validation["missing_review_ids"]
    assert any("not classified" in e for e in validation["errors"])


def test_validate_batch_duplicate_id():
    """Duplicate review ID is detected."""
    reviews = [_make_review(f"r{i:04d}") for i in range(2)]
    results = [
        _make_classification("r0000", themes=["T1"]),
        _make_classification("r0000", themes=["T5"]),  # duplicate
    ]
    original_ids = [r["review_id"] for r in reviews]
    validation = validate_batch_classification(results, original_ids)
    assert validation["valid"] is False
    assert any("Duplicate" in e for e in validation["errors"])


def test_validate_batch_unknown_id():
    """Unknown review ID is detected."""
    reviews = [_make_review("r0000")]
    results = [_make_classification("r9999", themes=["T1"])]  # not in input
    original_ids = [r["review_id"] for r in reviews]
    validation = validate_batch_classification(results, original_ids)
    assert validation["valid"] is False
    assert "r9999" in validation["extra_review_ids"]


def test_validate_batch_invalid_theme():
    """Invalid theme ID is detected."""
    reviews = [_make_review("r0000")]
    results = [_make_classification("r0000", themes=["T99"])]
    original_ids = ["r0000"]
    validation = validate_batch_classification(results, original_ids)
    assert validation["valid"] is False
    assert any("invalid theme" in e.lower() for e in validation["errors"])


def test_validate_batch_too_many_themes():
    """More than 2 themes per review is detected."""
    reviews = [_make_review("r0000")]
    results = [_make_classification("r0000", themes=["T1", "T2", "T3"])]
    original_ids = ["r0000"]
    validation = validate_batch_classification(results, original_ids)
    assert validation["valid"] is False
    assert any("max" in e.lower() and "theme" in e.lower() for e in validation["errors"])


def test_validate_batch_invalid_sentiment():
    """Invalid sentiment is detected."""
    reviews = [_make_review("r0000")]
    results = [_make_classification("r0000", themes=["T5"], sentiment="happy")]
    original_ids = ["r0000"]
    validation = validate_batch_classification(results, original_ids)
    assert validation["valid"] is False
    assert any("sentiment" in e.lower() for e in validation["errors"])


def test_validate_batch_invalid_fee_topic():
    """Invalid fee topic is detected."""
    reviews = [_make_review("r0000")]
    results = [_make_classification("r0000", themes=["T5"], fee_topic="brokerage_only")]
    original_ids = ["r0000"]
    validation = validate_batch_classification(results, original_ids)
    assert validation["valid"] is False
    assert any("fee topic" in e.lower() for e in validation["errors"])


def test_validate_batch_fee_topic_consistency():
    """Fee-topic consistency: T1 assigned ⟺ fee_topic != none."""
    reviews = [_make_review("r0000")]
    # T1 assigned but fee_topic=none -> questionable
    results = [_make_classification("r0000", themes=["T1"], sentiment="negative", fee_topic="none")]
    original_ids = ["r0000"]
    validation = validate_batch_classification(results, original_ids)
    assert validation["valid"] is True  # consistency is a warning, not error
    assert any("questionable" in w.lower() for w in validation["warnings"])

    # T1 not assigned but fee_topic=fee-brokerage -> questionable
    results2 = [_make_classification("r0000", themes=["T5"], sentiment="positive", fee_topic="fee-brokerage")]
    validation2 = validate_batch_classification(results2, original_ids)
    assert validation2["valid"] is True
    assert any("questionable" in w.lower() for w in validation2["warnings"])


def test_is_fee_questionable():
    """Fee-questionable detection."""
    assert is_fee_questionable({"themes": ["T1"], "fee_topic": "none"}) is True
    assert is_fee_questionable({"themes": ["T5"], "fee_topic": "fee-brokerage"}) is True
    assert is_fee_questionable({"themes": ["T1"], "fee_topic": "fee-brokerage"}) is False
    assert is_fee_questionable({"themes": ["T5"], "fee_topic": "none"}) is False


# ---------------------------------------------------------------------------
# Aggregation tests
# ---------------------------------------------------------------------------

def test_aggregate_theme_frequencies():
    """Theme frequencies are aggregated correctly."""
    results = [
        _make_classification("r1", themes=["T1"], sentiment="negative", fee_topic="fee-brokerage"),
        _make_classification("r2", themes=["T5"], sentiment="positive", fee_topic="none"),
        _make_classification("r3", themes=["T1", "T2"], sentiment="negative", fee_topic="fee-other"),
    ]
    agg = aggregate_theme_frequencies(results, "test_run")
    assert agg["total_reviews_classified"] == 3
    assert agg["theme_counts"]["T1"] == 2  # r1 and r3
    assert agg["theme_counts"]["T2"] == 1  # r3 only
    assert agg["theme_counts"]["T5"] == 1  # r2 only
    assert agg["sentiment_counts"]["negative"] == 2
    assert agg["sentiment_counts"]["positive"] == 1
    assert agg["fee_topic_counts"]["fee-brokerage"] == 1
    assert agg["fee_topic_counts"]["fee-other"] == 1
    assert agg["fee_topic_counts"]["none"] == 1


def test_aggregate_one_review_at_most_once_per_theme():
    """A review with 2 themes contributes 1 to each theme count."""
    results = [
        _make_classification("r1", themes=["T1", "T2"], sentiment="negative", fee_topic="fee-brokerage"),
    ]
    agg = aggregate_theme_frequencies(results, "test_run")
    assert agg["theme_counts"]["T1"] == 1
    assert agg["theme_counts"]["T2"] == 1
    assert agg["total_reviews_classified"] == 1


def test_aggregate_questionable_fees():
    """Questionable fee-subtype claims are flagged in aggregation."""
    results = [
        _make_classification("r1", themes=["T1"], sentiment="negative", fee_topic="none"),  # questionable
    ]
    agg = aggregate_theme_frequencies(results, "test_run")
    assert agg["questionable_fee_count"] == 1
    assert "r1" in agg["questionable_fee_review_ids"]


def test_aggregate_scope_labels():
    """Aggregation distinguishes pilot, initial test, and full counts."""
    results = [_make_classification("r1", themes=["T5"], sentiment="positive", fee_topic="none")]
    agg = aggregate_theme_frequencies(results, "phase_3_2_initial_test")
    assert agg["scope_labels"]["pilot_25_reviews"] == "separate_pilot_run"
    assert agg["scope_labels"]["initial_test_100_reviews"] == "phase_3_2_initial_test"
    assert agg["scope_labels"]["full_1000_reviews"] == "pending_scale_up_approval"


# ---------------------------------------------------------------------------
# Privacy tests
# ---------------------------------------------------------------------------

def test_quote_eligible_preserved_in_batch():
    """quote_eligible field is preserved through batch generation."""
    reviews = [
        _make_review("r1", quote_eligible="yes"),
        _make_review("r2", quote_eligible="no"),
    ]
    result = generate_batches(reviews, max_batches=1)
    batch = result["batches"][0]
    r1 = [r for r in batch["reviews"] if r["review_id"] == "r1"][0]
    r2 = [r for r in batch["reviews"] if r["review_id"] == "r2"][0]
    assert r1["quote_eligible"] == "yes"
    assert r2["quote_eligible"] == "no"


def test_no_original_text_in_sample():
    """Analysis sample does not contain original_review_text column."""
    sample_path = os.path.join(ROOT, "data", "analysis_sample.csv")
    if not os.path.exists(sample_path):
        # Skip if sample not generated yet
        return
    with open(sample_path, "r", newline="", encoding="utf-8") as f:
        header = f.readline()
    assert "original_review_text" not in header


def test_pii_redacted_flag_preserved():
    """pii_redacted flag is preserved through batch generation."""
    reviews = [
        _make_review("r1", pii_redacted="yes"),
        _make_review("r2", pii_redacted="no"),
    ]
    result = generate_batches(reviews, max_batches=1)
    batch = result["batches"][0]
    r1 = [r for r in batch["reviews"] if r["review_id"] == "r1"][0]
    r2 = [r for r in batch["reviews"] if r["review_id"] == "r2"][0]
    assert r1["pii_redacted"] == "yes"
    assert r2["pii_redacted"] == "no"


# ---------------------------------------------------------------------------
# Taxonomy JSON export test
# ---------------------------------------------------------------------------

def test_get_taxonomy_json():
    """Taxonomy can be exported as JSON for prompt inclusion."""
    taxonomy_json = get_taxonomy_json()
    parsed = json.loads(taxonomy_json)
    assert len(parsed) == 5
    assert "T1" in parsed
    assert "T5" in parsed
