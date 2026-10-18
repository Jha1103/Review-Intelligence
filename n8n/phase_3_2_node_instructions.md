# Phase 3.2 — n8n Node-by-Node Instructions (Self-Hosted CE 2.43.7)

This document provides precise instructions for extending the existing n8n
workflow with scalable, auditable classification for the 1,000-review sample.

**Prerequisite:** The existing workflow ends at "Validate AI Pilot Results"
after a successful 25-review pilot. Phase 3.2 extends AFTER "Validate Review
Dataset" succeeds, using ALL 1,000 Google Sheets review records.

**Important:** Do not overwrite the existing workflow. Add these nodes as an
extension branch. Do not change credentials. Do not call Gemini until you
approve the 100-review test.

---

## Overview of New Nodes

| # | Node Name | Type | Purpose |
|---|-----------|------|---------|
| 1 | Generate Classification Batches | Code (JavaScript) | Splits 1,000 reviews into batches of 25 (max 4 batches = 100 reviews for initial test) |
| 2 | Gemini Classify Batch | Google Gemini | Calls Gemini with classification prompt for each batch |
| 3 | Validate Batch Classification | Code (JavaScript) | Deterministic validation of Gemini results per batch |
| 4 | Store Batch Results | Code (JavaScript) | Stores validated results with batch metadata for audit/resume |
| 5 | Aggregate Classification Results | Code (JavaScript) | Aggregates theme frequencies across all batches |
| 6 | Check More Batches | IF | Routes to process more batches or proceed to aggregation |

---

## Node 1 — Generate Classification Batches (Code)

**Type:** Code (JavaScript)  
**Position:** After "Validate Review Dataset"  
**Input:** 1 item containing all 1,000 reviews from Google Sheets

### JavaScript Code

```javascript
// Phase 3.2 — Generate Classification Batches
// Input: 1 item with all reviews from Validate Review Dataset
// Output: N items (one per batch), max 4 batches for initial test (100 reviews)

const BATCH_SIZE = 25;
const MAX_BATCHES_FOR_TEST = 4; // 4 x 25 = 100 reviews
const RUN_ID = `run_${Date.now()}`;

// Get the reviews array from input
// The input item may have reviews in different fields depending on upstream node
let reviews = [];
const inputJson = $input.first().json;

// Try to find reviews array in common locations
if (inputJson.reviews) {
  reviews = inputJson.reviews;
} else if (inputJson.data && inputJson.data.reviews) {
  reviews = inputJson.data.reviews;
} else if (Array.isArray(inputJson)) {
  reviews = inputJson;
} else {
  // If input is a single item with review fields directly
  reviews = [inputJson];
}

// Sort by review_id for deterministic ordering
reviews.sort((a, b) => (a.review_id || "").localeCompare(b.review_id || ""));

// Generate batches
const batches = [];
const numBatches = Math.min(
  MAX_BATCHES_FOR_TEST,
  Math.ceil(reviews.length / BATCH_SIZE)
);

for (let i = 0; i < numBatches; i++) {
  const start = i * BATCH_SIZE;
  const end = Math.min(start + BATCH_SIZE, reviews.length);
  const batchReviews = reviews.slice(start, end);
  const batchId = `batch_${i + 1}_${String(Date.now()).slice(-6)}`;

  batches.push({
    batch_id: batchId,
    batch_index: i + 1,
    run_id: RUN_ID,
    batch_size: BATCH_SIZE,
    review_count: batchReviews.length,
    review_ids: batchReviews.map(r => r.review_id),
    reviews: batchReviews,
    status: "pending",
    created_at: new Date().toISOString(),
  });
}

// Return one item per batch
return batches.map(b => ({ json: b }));
```

### Parameters
- **Operation:** Run once for all items (not per item)

---

## Node 2 — Gemini Classify Batch (Google Gemini)

**Type:** Google Gemini (Chat Model)  
**Position:** After "Generate Classification Batches"  
**Input:** 1 item per batch (25 reviews)

### Configuration
- **Model:** gemini-1.5-flash (verify supported model in your n8n instance)
- **Temperature:** 0.1 (deterministic)
- **Max Output Tokens:** 4096
- **API Key:** Configured in n8n credentials (do not hardcode)

### System Message (from docs/GEMINI_CLASSIFICATION_PROMPT.md)

Copy the full system instructions from `docs/GEMINI_CLASSIFICATION_PROMPT.md`.

### User Message (constructed in Code node before this, or use expressions)

The user message should contain the batch of 25 reviews as a JSON array. Use
n8n expressions to pass the `reviews` field from the previous node.

Example expression for the prompt content:
```
{{ $json.reviews | JSON.stringify }}
```

### Important
- Only `cleaned_review_text` (PII-redacted) is sent to Gemini.
- Original `original_review_text` is NEVER in the Google Sheets data (it's in
  the private local cleaned_reviews.csv only).
- Reviews with `quote_eligible=no` are still classified but flagged.

---

## Node 3 — Validate Batch Classification (Code, JavaScript)

**Type:** Code (JavaScript)  
**Position:** After "Gemini Classify Batch"  
**Input:** 1 item (Gemini response + original batch data)

### JavaScript Code

```javascript
// Phase 3.2 — Validate Batch Classification (JavaScript)
// Input: Gemini classification results + original batch review IDs
// Output: Validated results or error

const VALID_THEME_IDS = ["T1", "T2", "T3", "T4", "T5"];
const VALID_SENTIMENTS = ["positive", "negative", "neutral"];
const VALID_FEE_TOPICS = ["fee-brokerage", "fee-other", "none"];
const MAX_THEMES_PER_REVIEW = 2;

const errors = [];
const warnings = [];
const classifiedIds = [];

// Get Gemini results
let geminiResults = [];
try {
  // Gemini node may return results in different formats
  const geminiOutput = $input.first().json;
  if (geminiOutput.classifications) {
    geminiResults = geminiOutput.classifications;
  } else if (geminiOutput.results) {
    geminiResults = geminiOutput.results;
  } else if (Array.isArray(geminiOutput)) {
    geminiResults = geminiOutput;
  } else if (geminiOutput.content) {
    // Try to parse JSON from content string
    geminiResults = JSON.parse(geminiOutput.content);
  }
} catch (e) {
  errors.push(`Failed to parse Gemini response: ${e.message}`);
  return [{ json: { valid: false, errors, warnings, classified_ids: [] } }];
}

// Get original review IDs from the batch (from previous node)
const originalReviewIds = ($input.first().json.review_ids || []).map(String);
const expectedIds = new Set(originalReviewIds);

// Check record count
if (geminiResults.length !== expectedIds.size) {
  errors.push(
    `Record count mismatch: expected ${expectedIds.size} classifications, got ${geminiResults.length}`
  );
}

const seenIds = new Set();

for (let i = 0; i < geminiResults.length; i++) {
  const result = geminiResults[i];
  const rid = String(result.review_id || "");

  // Duplicate check
  if (seenIds.has(rid)) {
    errors.push(`Duplicate review ID in batch results: ${rid}`);
    continue;
  }
  seenIds.add(rid);

  // Unknown ID check
  if (!expectedIds.has(rid)) {
    errors.push(`Unknown review ID in batch results: ${rid}`);
    continue;
  }

  classifiedIds.push(rid);

  // Validate themes
  const themes = result.themes || [];
  if (!Array.isArray(themes)) {
    errors.push(`Review ${rid}: themes is not a list`);
    continue;
  }
  if (themes.length > MAX_THEMES_PER_REVIEW) {
    errors.push(
      `Review ${rid}: ${themes.length} themes assigned, max ${MAX_THEMES_PER_REVIEW} allowed`
    );
  }
  const invalidThemes = themes.filter(t => !VALID_THEME_IDS.includes(t));
  if (invalidThemes.length > 0) {
    errors.push(`Review ${rid}: invalid theme IDs: ${JSON.stringify(invalidThemes)}`);
  }

  // Validate sentiment
  const sentiment = result.sentiment || "";
  if (!VALID_SENTIMENTS.includes(sentiment)) {
    errors.push(`Review ${rid}: invalid sentiment '${sentiment}'`);
  }

  // Validate fee topic
  const feeTopic = result.fee_topic || "none";
  if (!VALID_FEE_TOPICS.includes(feeTopic)) {
    errors.push(`Review ${rid}: invalid fee topic '${feeTopic}'`);
  }

  // Fee-topic consistency check
  const isFee = themes.includes("T1");
  const hasFeeTopic = feeTopic !== "none";
  if (isFee !== hasFeeTopic) {
    warnings.push(
      `Review ${rid}: questionable fee-subtype claim (T1=${isFee}, fee_topic=${feeTopic}), flagged for manual review`
    );
  }
}

// Missing classifications
const missingIds = [...expectedIds].filter(id => !seenIds.has(id));
for (const rid of missingIds) {
  errors.push(`Review ${rid}: not classified (missing from results)`);
}

// Extra classifications
const extraIds = [...seenIds].filter(id => !expectedIds.has(id));
for (const rid of extraIds) {
  errors.push(`Review ${rid}: classified but not in input batch`);
}

const valid = errors.length === 0;

return [{
  json: {
    valid,
    batch_id: $input.first().json.batch_id,
    batch_index: $input.first().json.batch_index,
    run_id: $input.first().json.run_id,
    errors,
    warnings,
    classified_review_ids: classifiedIds.sort(),
    missing_review_ids: missingIds.sort(),
    extra_review_ids: extraIds.sort(),
    classified_count: classifiedIds.length,
    input_count: expectedIds.size,
    gemini_results: geminiResults,
    validated_at: new Date().toISOString(),
  },
}];
```

### Parameters
- **Operation:** Run once for each item

---

## Node 4 — Store Batch Results (Code, JavaScript)

**Type:** Code (JavaScript)  
**Position:** After "Validate Batch Classification"  
**Input:** 1 item (validated batch results)

### JavaScript Code

```javascript
// Phase 3.2 — Store Batch Results
// Input: Validated batch classification results
// Output: Stored confirmation with batch metadata

const validation = $input.first().json;

const storeRecord = {
  batch_id: validation.batch_id,
  batch_index: validation.batch_index,
  run_id: validation.run_id,
  status: validation.valid ? "completed" : "failed",
  review_count: validation.input_count,
  classified_count: validation.classified_count,
  error_count: validation.errors.length,
  warning_count: validation.warnings.length,
  classified_review_ids: validation.classified_review_ids,
  missing_review_ids: validation.missing_review_ids,
  questionable_fee_warnings: validation.warnings.filter(w =>
    w.includes("questionable fee-subtype")
  ),
  validated_at: validation.validated_at,
  errors: validation.errors,
  warnings: validation.warnings,
};

// In production, this would append to Google Sheets or n8n Data Tables.
// For now, return the record so it can be collected by the aggregation node.
return [{ json: storeRecord }];
```

---

## Node 5 — Check More Batches (IF)

**Type:** IF  
**Position:** After "Store Batch Results"  
**Purpose:** Route to process more batches or proceed to aggregation

### Configuration
- **Condition:** `{{ $json.batch_index < 4 }}` (true = more batches for initial test)
- **True output:** Route back to process next batch (via n8n's native item processing — each batch item already flows through independently)
- **False output:** Proceed to "Aggregate Classification Results"

### Note on n8n Looping

n8n CE processes each batch item independently through Nodes 2-4. Since Node 1
produces 4 items (one per batch), n8n processes all 4 through the Gemini →
Validate → Store chain automatically. The IF node is informational for the
initial test limit; in production, remove the IF and let all batches process.

For resume safety: store batch results with `batch_id` and `status`. On
re-run, skip batches with `status === "completed"`.

---

## Node 6 — Aggregate Classification Results (Code, JavaScript)

**Type:** Code (JavaScript)  
**Position:** After all batches processed  
**Input:** All validated batch results (4 items for initial test)

### JavaScript Code

```javascript
// Phase 3.2 — Aggregate Classification Results
// Input: All validated batch classification results
// Output: Aggregated theme frequencies with run labels

const VALID_THEME_IDS = ["T1", "T2", "T3", "T4", "T5"];
const VALID_SENTIMENTS = ["positive", "negative", "neutral"];
const VALID_FEE_TOPICS = ["fee-brokerage", "fee-other", "none"];

// Collect all results from all batch items
const allResults = [];
const batchSummaries = [];

for (const item of $input.all()) {
  const json = item.json;
  if (json.gemini_results) {
    allResults.push(...json.gemini_results);
  }
  batchSummaries.push({
    batch_id: json.batch_id,
    batch_index: json.batch_index,
    status: json.status,
    review_count: json.review_count,
    classified_count: json.classified_count,
    error_count: json.error_count,
    warning_count: json.warning_count,
  });
}

// Aggregate theme frequencies (one review at most once per theme)
const themeCounts = {};
VALID_THEME_IDS.forEach(tid => { themeCounts[tid] = 0; });

const sentimentCounts = {};
VALID_SENTIMENTS.forEach(s => { sentimentCounts[s] = 0; });

const feeTopicCounts = {};
VALID_FEE_TOPICS.forEach(ft => { feeTopicCounts[ft] = 0; });

let totalReviews = 0;
let reviewsWithThemes = 0;
const questionableFees = [];

for (const result of allResults) {
  totalReviews++;
  const themes = result.themes || [];
  const sentiment = result.sentiment || "";
  const feeTopic = result.fee_topic || "none";

  if (themes.length > 0) {
    reviewsWithThemes++;
    for (const tid of themes) {
      if (themeCounts[tid] !== undefined) {
        themeCounts[tid]++;
      }
    }
  }

  if (sentimentCounts[sentiment] !== undefined) {
    sentimentCounts[sentiment]++;
  }

  if (feeTopicCounts[feeTopic] !== undefined) {
    feeTopicCounts[feeTopic]++;
  }

  // Flag questionable fee-subtype claims
  const isFee = themes.includes("T1");
  const hasFeeTopic = feeTopic !== "none";
  if (isFee !== hasFeeTopic) {
    questionableFees.push(result.review_id);
  }
}

// Distinguish count scopes
const SCOPE = "phase_3_2_initial_test"; // 100 reviews, 4 batches

return [{
  json: {
    run_id: $input.first().json.run_id || "unknown",
    scope: SCOPE,
    total_reviews_classified: totalReviews,
    reviews_with_themes: reviewsWithThemes,
    batch_count: batchSummaries.length,
    batch_summaries: batchSummaries,
    theme_counts: themeCounts,
    sentiment_counts: sentimentCounts,
    fee_topic_counts: feeTopicCounts,
    questionable_fee_review_ids: questionableFees,
    questionable_fee_count: questionableFees.length,
    classification_complete: totalReviews > 0,
    aggregated_at: new Date().toISOString(),
    // Scope labels for reporting
    scope_labels: {
      pilot_25_reviews: "separate_pilot_run",
      initial_test_100_reviews: SCOPE,
      full_1000_reviews: "pending_scale_up_approval",
    },
  },
}];
```

---

## Error Handling & Retries

### Gemini Node Retry Configuration
- **Retry On Fail:** Enable
- **Max Retries:** 3
- **Retry Wait:** 5s, 10s, 20s (exponential backoff)
- **Retry On:** Temporary errors (rate limits, network, 5xx)

### Validation Failure Handling
- If validation fails (`valid === false`), the batch is marked `status: "failed"` with errors recorded
- Failed batches are NOT silently skipped
- The aggregation node reports `error_count` per batch
- Manual intervention required for failed batches

### Resume Safety
- Each batch result includes `batch_id`, `batch_index`, `status`
- On re-run, check existing results and skip `status === "completed"` batches
- Never double-count a review in theme frequencies

---

## Data Flow Summary

```
Validate Review Dataset (succeeds)
        │
        ▼
Generate Classification Batches (4 batches × 25 reviews)
        │
        ├─► Batch 1 ──► Gemini Classify ──► Validate ──► Store
        ├─► Batch 2 ──► Gemini Classify ──► Validate ──► Store
        ├─► Batch 3 ──► Gemini Classify ──► Validate ──► Store
        └─► Batch 4 ──► Gemini Classify ──► Validate ──► Store
        │
        ▼
Aggregate Classification Results (theme frequencies, 100-review scope)
```

---

## What Must Be Manually Tested in n8n

1. **Google Sheets connection:** Verify "Get Row(s)" returns all 1,000 reviews from the correct sheet
2. **Gemini credentials:** Verify the Gemini API key is configured in n8n credentials
3. **Model name:** Verify `gemini-1.5-flash` (or your available model) works in your n8n instance
4. **Batch count:** Verify Node 1 produces exactly 4 batches for the initial test
5. **Validation logic:** Run once and confirm all 4 batches pass validation
6. **Aggregation:** Confirm theme counts sum correctly across 4 batches
7. **Error handling:** Temporarily break Gemini input to confirm validation catches errors
8. **Privacy:** Confirm `original_review_text` is never in the Google Sheets data sent to Gemini

---

## Files Reference

| File | Purpose |
|------|---------|
| `docs/GEMINI_CLASSIFICATION_PROMPT.md` | Full Gemini system prompt |
| `src/taxonomy.py` | Theme taxonomy (Python reference) |
| `src/batch_generator.py` | Deterministic batch generation (Python reference) |
| `src/batch_validator.py` | Batch validation logic (Python reference) |
| `tests/test_phase_3_2.py` | Automated local tests |
| `n8n/phase_3_2_workflow.json` | Workflow JSON (reference, may need adjustment) |
