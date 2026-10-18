"""Automated tests for Phase 3.2 — Review Classification (synthetic fixtures only).

Tests taxonomy, batch generation, validation, and aggregation logic using
synthetic fixtures. Never mixes synthetic test reviews with genuine output data.

Regression tests for critical defects:
- Missing batch metadata
- Lost classification data
- Unclear reviews (empty themes array)
- Incomplete aggregation (missing/failed batches)
- Fee vocabulary and sentiment values
- Deterministic selection (not first 100 alphabetically)
- Response parsing from content.parts[0].text
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
    DETERMINISTIC_SEED,
    get_theme_name,
    validate_theme_ids,
    validate_sentiment,
    validate_fee_topic,
    is_fee_related,
    is_fee_questionable,
    get_taxonomy_json,
)
from batch_generator import (  # noqa: E402
    load_sample_reviews,
    deterministic_batch_id,
    select_100_deterministically,
    generate_batches,
)
from batch_validator import (  # noqa: E402
    validate_batch_classification,
    parse_gemini_response_text,
    extract_classifications_from_gemini_response,
    is_fee_questionable as bv_is_fee_questionable,
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


def _make_classification(review_id, themes=None, sentiment="positive",
                          fee_topic="none", needs_manual_review=False,
                          reasoning="Test review"):
    if themes is None:
        themes = ["T5"]
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
    """Taxonomy contains exactly 5 themes."""
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


def test_validate_theme_ids_allows_empty():
    """Empty theme list is valid (unclassified)."""
    assert validate_theme_ids([]) is True
    assert validate_theme_ids(["T1", "T2"]) is True
    assert validate_theme_ids(["T99"]) is False
    assert validate_theme_ids(["T1", "T99"]) is False
    assert validate_theme_ids("T1") is False  # not a list


def test_validate_sentiment_includes_unclear_mixed():
    """Sentiments include unclear and mixed."""
    for s in VALID_SENTIMENTS:
        assert validate_sentiment(s) is True
    assert "unclear" in VALID_SENTIMENTS
    assert "mixed" in VALID_SENTIMENTS
    assert validate_sentiment("happy") is False


def test_validate_fee_topic_vocabulary():
    """Fee topics match pilot vocabulary."""
    expected = {"brokerage", "dp_charges", "other_fee", "unspecified_fee", "none", "unclear"}
    assert VALID_FEE_TOPICS == expected
    for ft in VALID_FEE_TOPICS:
        assert validate_fee_topic(ft) is True
    assert validate_fee_topic("fee-brokerage") is False  # old vocab, not valid
    assert validate_fee_topic("fee-other") is False      # old vocab, not valid


def test_is_fee_related():
    """Fee-related theme detection."""
    assert is_fee_related(["T1"]) is True
    assert is_fee_related(["T1", "T2"]) is True
    assert is_fee_related(["T2"]) is False
    assert is_fee_related([]) is False
    assert is_fee_related(["T5"]) is False


def test_max_themes_per_review():
    """Maximum 2 themes per review enforced."""
    assert MAX_THEMES_PER_REVIEW == 2


# ---------------------------------------------------------------------------
# Batch generation tests
# ---------------------------------------------------------------------------

def test_generate_batches_deterministic():
    """Same input produces same batches."""
    reviews = [_make_review(f"r{i:04d}", rating=(i % 5) + 1) for i in range(1000)]
    result1 = generate_batches(reviews, seed=42, run_id="run_a")
    result2 = generate_batches(reviews, seed=42, run_id="run_a")
    assert result1["run_id"] == result2["run_id"]
    assert result1["num_batches"] == result2["num_batches"]
    for b1, b2 in zip(result1["batches"], result2["batches"]):
        assert b1["batch_id"] == b2["batch_id"]
        assert b1["review_ids"] == b2["review_ids"]


def test_generate_batches_no_duplicates():
    """No review appears in more than one batch."""
    reviews = [_make_review(f"r{i:04d}") for i in range(1000)]
    result = generate_batches(reviews)
    all_ids = [rid for b in result["batches"] for rid in b["review_ids"]]
    assert len(all_ids) == len(set(all_ids)), "Review ID appears in multiple batches"


def test_generate_batches_exactly_100_reviews():
    """Exactly 100 reviews across 4 batches of 25."""
    reviews = [_make_review(f"r{i:04d}") for i in range(1000)]
    result = generate_batches(reviews)
    assert result["num_batches"] == 4
    assert result["reviews_selected_for_test"] == 100
    assert result["total_reviews_in_batches"] == 100
    for b in result["batches"]:
        assert b["review_count"] == 25


def test_generate_batches_not_first_100_alphabetically():
    """Selection is NOT simply the first 100 alphabetically sorted review IDs."""
    reviews = [_make_review(f"r{i:04d}") for i in range(1000)]
    result = generate_batches(reviews)
    all_selected_ids = [rid for b in result["batches"] for rid in b["review_ids"]]
    # First 100 alphabetically would be r0000 through r0099
    first_100_alpha = [f"r{i:04d}" for i in range(100)]
    assert all_selected_ids != first_100_alpha, (
        "Selection should not be first 100 alphabetically"
    )


def test_generate_batches_selection_method_documented():
    """Selection method and seed are documented."""
    reviews = [_make_review(f"r{i:04d}") for i in range(1000)]
    result = generate_batches(reviews)
    assert result["seed"] == 42
    assert "systematic_step_10_seed_42" in result["selection_method"]
    assert result["source_dataset"] == "analysis_sample_1000"


def test_deterministic_batch_id():
    """Batch IDs are deterministic."""
    bid1 = deterministic_batch_id("run_1", 1)
    bid2 = deterministic_batch_id("run_1", 1)
    bid3 = deterministic_batch_id("run_2", 1)
    assert bid1 == bid2
    assert bid1 != bid3


def test_batch_ids_unique():
    """Generated batch IDs are unique."""
    reviews = [_make_review(f"r{i:04d}") for i in range(1000)]
    result = generate_batches(reviews)
    batch_ids = [b["batch_id"] for b in result["batches"]]
    assert len(batch_ids) == len(set(batch_ids))


def test_select_100_deterministically_wrong_count():
    """Selection raises error if input is not 1,000 reviews."""
    reviews = [_make_review(f"r{i:04d}") for i in range(500)]
    try:
        select_100_deterministically(reviews)
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "1000" in str(e)


# ---------------------------------------------------------------------------
# Batch validation tests
# ---------------------------------------------------------------------------

def test_validate_batch_all_valid():
    """Valid batch classification passes validation."""
    reviews = [_make_review(f"r{i:04d}") for i in range(3)]
    results = [
        _make_classification("r0000", themes=["T1"], sentiment="negative", fee_topic="brokerage"),
        _make_classification("r0001", themes=["T5"], sentiment="positive", fee_topic="none"),
        _make_classification("r0002", themes=["T2", "T3"], sentiment="mixed", fee_topic="none"),
    ]
    original_ids = [r["review_id"] for r in reviews]
    validation = validate_batch_classification(results, original_ids)
    assert validation["valid"] is True
    assert validation["errors"] == []
    assert len(validation["classified_review_ids"]) == 3


def test_validate_batch_unclear_review_empty_themes():
    """Unclear review with empty themes array is valid."""
    reviews = [_make_review("r0000")]
    results = [_make_classification("r0000", themes=[], sentiment="unclear", fee_topic="none")]
    original_ids = ["r0000"]
    validation = validate_batch_classification(results, original_ids)
    assert validation["valid"] is True
    assert validation["classified_review_ids"] == ["r0000"]


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
    original_ids = ["r0000"]
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
    results = [_make_classification("r0000", themes=["T5"], fee_topic="fee-brokerage")]
    original_ids = ["r0000"]
    validation = validate_batch_classification(results, original_ids)
    assert validation["valid"] is False
    assert any("fee topic" in e.lower() for e in validation["errors"])


def test_validate_batch_fee_topic_consistency():
    """Fee-topic consistency: T1 assigned ⟺ fee_topic is a specific subtype."""
    # T1 assigned but fee_topic=none -> questionable warning
    reviews = [_make_review("r0000")]
    results = [_make_classification("r0000", themes=["T1"], sentiment="negative", fee_topic="none")]
    original_ids = ["r0000"]
    validation = validate_batch_classification(results, original_ids)
    assert validation["valid"] is True  # consistency is a warning, not error
    assert any("questionable" in w.lower() for w in validation["warnings"])

    # T1 not assigned but fee_topic=brokerage -> questionable warning
    results2 = [_make_classification("r0000", themes=["T5"], sentiment="positive", fee_topic="brokerage")]
    validation2 = validate_batch_classification(results2, original_ids)
    assert validation2["valid"] is True
    assert any("questionable" in w.lower() for w in validation2["warnings"])

    # Consistent: T1 + brokerage -> no warning
    results3 = [_make_classification("r0000", themes=["T1"], sentiment="negative", fee_topic="brokerage")]
    validation3 = validate_batch_classification(results3, original_ids)
    assert validation3["valid"] is True
    assert not any("questionable" in w.lower() for w in validation3["warnings"])


def test_is_fee_questionable_new_vocab():
    """Fee-questionable detection with new vocabulary."""
    assert bv_is_fee_questionable({"themes": ["T1"], "fee_topic": "none"}) is True
    assert bv_is_fee_questionable({"themes": ["T5"], "fee_topic": "brokerage"}) is True
    assert bv_is_fee_questionable({"themes": ["T1"], "fee_topic": "brokerage"}) is False
    assert bv_is_fee_questionable({"themes": [], "fee_topic": "none"}) is False
    assert bv_is_fee_questionable({"themes": ["T1"], "fee_topic": "dp_charges"}) is False


# ---------------------------------------------------------------------------
# Gemini response parsing tests
# ---------------------------------------------------------------------------

def test_parse_gemini_response_text_valid():
    """Parse valid Gemini response text from content.parts[0].text."""
    raw_text = '[{"review_id": "r1", "themes": ["T1"], "sentiment": "negative", "fee_topic": "brokerage"}]'
    result = parse_gemini_response_text(raw_text)
    assert len(result) == 1
    assert result[0]["review_id"] == "r1"


def test_parse_gemini_response_text_with_markdown():
    """Parse Gemini response wrapped in markdown code fences."""
    raw_text = "```json\n[{\"review_id\": \"r1\", \"themes\": [\"T1\"]}]\n```"
    result = parse_gemini_response_text(raw_text)
    assert len(result) == 1
    assert result[0]["review_id"] == "r1"


def test_parse_gemini_response_text_empty():
    """Empty text raises ValueError."""
    try:
        parse_gemini_response_text("")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "empty" in str(e).lower()


def test_parse_gemini_response_text_no_array():
    """Text without JSON array raises ValueError."""
    try:
        parse_gemini_response_text("no json here")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "No JSON array found" in str(e)


def test_extract_classifications_from_gemini_response():
    """Extract classifications from full Gemini node output structure."""
    gemini_output = {
        "content": {
            "parts": [
                {
                    "text": '[{"review_id": "r1", "themes": ["T1"], "sentiment": "negative", "fee_topic": "brokerage"}]'
                }
            ]
        }
    }
    result = extract_classifications_from_gemini_response(gemini_output)
    assert len(result) == 1
    assert result[0]["review_id"] == "r1"
    assert result[0]["themes"] == ["T1"]


def test_extract_classifications_missing_parts():
    """Missing content.parts raises ValueError."""
    try:
        extract_classifications_from_gemini_response({"content": {}})
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "parts" in str(e).lower()


def test_extract_classifications_missing_text():
    """Missing content.parts[0].text raises ValueError."""
    try:
        extract_classifications_from_gemini_response({"content": {"parts": [{}]}})
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "text" in str(e).lower()


# ---------------------------------------------------------------------------
# Aggregation tests
# ---------------------------------------------------------------------------

def test_aggregate_theme_frequencies():
    """Theme frequencies are aggregated correctly."""
    results = [
        _make_classification("r1", themes=["T1"], sentiment="negative", fee_topic="brokerage"),
        _make_classification("r2", themes=["T5"], sentiment="positive", fee_topic="none"),
        _make_classification("r3", themes=["T1", "T2"], sentiment="negative", fee_topic="other_fee"),
    ]
    agg = aggregate_theme_frequencies(results, "test_run", require_full_count=False)
    assert agg["total_reviews_classified"] == 3
    assert agg["theme_counts"]["T1"] == 2  # r1 and r3
    assert agg["theme_counts"]["T2"] == 1  # r3 only
    assert agg["theme_counts"]["T5"] == 1  # r2 only


def test_aggregate_one_review_at_most_once_per_theme():
    """A review with 2 themes contributes 1 to each theme count."""
    results = [
        _make_classification("r1", themes=["T1", "T2"], sentiment="negative", fee_topic="brokerage"),
    ]
    agg = aggregate_theme_frequencies(results, "test_run", require_full_count=False)
    assert agg["theme_counts"]["T1"] == 1
    assert agg["theme_counts"]["T2"] == 1
    assert agg["total_reviews_classified"] == 1


def test_aggregate_questionable_fees():
    """Questionable fee-subtype claims are flagged in aggregation."""
    results = [
        _make_classification("r1", themes=["T1"], sentiment="negative", fee_topic="none"),  # questionable
    ]
    agg = aggregate_theme_frequencies(results, "test_run", require_full_count=False)
    assert agg["questionable_fee_count"] == 1
    assert "r1" in agg["questionable_fee_review_ids"]


def test_aggregate_scope_labels():
    """Aggregation distinguishes pilot, initial test, and full counts."""
    results = [_make_classification("r1", themes=["T5"], sentiment="positive", fee_topic="none")]
    agg = aggregate_theme_frequencies(results, "phase_3_2_initial_test", require_full_count=False)
    assert agg["scope_labels"]["pilot_25_reviews"] == "separate_pilot_run"
    assert agg["scope_labels"]["initial_test_100_reviews"] == "phase_3_2_initial_test"
    assert agg["scope_labels"]["full_1000_reviews"] == "pending_scale_up_approval"


def test_aggregate_requires_exactly_100_unique():
    """Aggregation fails if not exactly 100 unique classified reviews."""
    # Too few
    results_few = [_make_classification("r1", themes=["T5"], sentiment="positive", fee_topic="none")]
    try:
        aggregate_theme_frequencies(results_few, "test_run")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "100" in str(e)

    # Duplicates
    results_dup = [
        _make_classification("r1", themes=["T5"], sentiment="positive", fee_topic="none"),
        _make_classification("r1", themes=["T5"], sentiment="positive", fee_topic="none"),
    ]
    try:
        aggregate_theme_frequencies(results_dup, "test_run")
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "duplicate" in str(e).lower() or "100" in str(e)


# ---------------------------------------------------------------------------
# Privacy tests
# ---------------------------------------------------------------------------

def test_quote_eligible_preserved_in_batch():
    """quote_eligible field is preserved through deterministic batch generation."""
    # Create 1000 reviews with alternating quote_eligible values
    reviews = [
        _make_review(f"x{i:04d}", quote_eligible="yes" if i % 2 == 0 else "no")
        for i in range(1000)
    ]

    result = generate_batches(reviews)  # 4 batches, 100 reviews

    # All 100 selected reviews should have valid quote_eligible values
    all_batch_reviews = [r for b in result["batches"] for r in b["reviews"]]
    assert len(all_batch_reviews) == 100
    for r in all_batch_reviews:
        assert r["quote_eligible"] in ("yes", "no"), (
            f"quote_eligible not preserved for {r['review_id']}: {r['quote_eligible']!r}"
        )


def test_no_original_text_in_sample():
    """Analysis sample does not contain original_review_text column."""
    sample_path = os.path.join(ROOT, "data", "analysis_sample.csv")
    if not os.path.exists(sample_path):
        return  # Skip if sample not generated yet
    with open(sample_path, "r", newline="", encoding="utf-8") as f:
        header = f.readline()
    assert "original_review_text" not in header


def test_pii_redacted_flag_preserved():
    """pii_redacted flag is preserved through batch generation."""
    reviews = [
        _make_review(f"x{i:04d}", pii_redacted="yes" if i % 3 == 0 else "no")
        for i in range(1000)
    ]

    result = generate_batches(reviews)

    all_batch_reviews = [r for b in result["batches"] for r in b["reviews"]]
    assert len(all_batch_reviews) == 100
    for r in all_batch_reviews:
        assert r["pii_redacted"] in ("yes", "no"), (
            f"pii_redacted not preserved for {r['review_id']}: {r['pii_redacted']!r}"
        )


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
