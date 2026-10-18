# Phase 3.2 — Extending the Existing n8n CE 2.43.7 Workflow

**Existing working workflow (DO NOT OVERWRITE):**

```
Manual Trigger → Get row(s) in sheet → Validate Review Dataset → Prepare AI Pilot → Google Gemini Message a Model → Validate AI Pilot Results
```

**Verified facts from live executions:**
- Google Sheets Get Row(s) outputs 1,000 individual items
- Validate Review Dataset outputs ONE summary item (not 1,000 reviews)
- Prepare AI Pilot reads original records using `$("Get row(s) in sheet").all()`
- Gemini successfully processed 25 reviews via `content.parts[0].text`
- The pilot validator parsed `content.parts[0].text` and checked 25 review IDs
- Google Gemini credentials already configured
- Worksheet: `analysis_sample`
- Model: whichever you selected in the existing live node (DO NOT change)

---

## Extension Point

Add Phase 3.2 as a branch that runs **AFTER** "Validate Review Dataset" succeeds.
The new branch reads the 1,000 reviews from the Google Sheets node (not from
Validate Review Dataset's summary output), selects 100 deterministically, and
processes them in 4 batches of 25 through Gemini.

**Do not modify or replace any existing nodes.** Add new nodes only.

---

## New Node 1 — Assert Validation Passed (Code)

**Type:** Code (JavaScript)  
**Position:** After "Validate Review Dataset"  
**Operation:** Run once for all items

### Purpose
Gate the batch generation on successful validation. Assert that
`validation_passed === true` before proceeding.

### JavaScript Code

```javascript
// Phase 3.2 — Gate: Assert Validation Passed
// Input: 1 item from Validate Review Dataset (summary only)
// Output: Passes through to batch generation if validation passed

const validation = $input.first().json;

if (!validation || validation.validation_passed !== true) {
  throw new Error(
    "Phase 3.2 blocked: Validate Review Dataset did not pass. " +
    "validation_passed = " + (validation ? validation.validation_passed : "undefined")
  );
}

// Pass through a minimal payload; the batch generator reads the 1,000 reviews
// directly from the Google Sheets node.
return [{
  json: {
    validation_passed: true,
    validated_at: validation.validated_at || new Date().toISOString(),
    proceed_to_batch_generation: true,
  },
}];
```

### Parameters
- **Operation:** Run once for all items

---

## New Node 2 — Generate Classification Batches (Code)

**Type:** Code (JavaScript)  
**Position:** After "Assert Validation Passed"  
**Operation:** Run once for all items

### Purpose
Read all 1,000 review records from the Google Sheets node using
`$("Get row(s) in sheet").all()`, select 100 deterministically (seed=42),
and split into 4 batches of 25.

### JavaScript Code

```javascript
// Phase 3.2 — Generate Classification Batches
// Input: 1 item (validation gate output)
// Output: 4 items (one per batch of 25 reviews)

// --- Configuration ---
const BATCH_SIZE = 25;
const MAX_BATCHES = 4;           // 4 x 25 = 100 reviews
const TOTAL_REVIEWS = 1000;
const SELECTED_COUNT = 100;
const SEED = 42;                 // Documented: deterministic selection seed
const SELECTION_METHOD = "systematic_step_10_seed_42";

// --- Gate check ---
if ($input.first().json.proceed_to_batch_generation !== true) {
  throw new Error("Phase 3.2 blocked: validation gate did not pass");
}

// --- Read all 1,000 reviews from the Google Sheets node ---
// NOTE: Validate Review Dataset outputs only a summary item.
// Use the Google Sheets node directly to get all individual review items.
let allReviews = [];
try {
  const sheetItems = $("Get row(s) in sheet").all();
  for (const item of sheetItems) {
    if (item.json && item.json.review_id) {
      allReviews.push(item.json);
    }
  }
} catch (e) {
  throw new Error(
    "Phase 3.2: Failed to read reviews from Google Sheets node. " +
    "Ensure the node is named exactly 'Get row(s) in sheet'. Error: " + e.message
  );
}

if (allReviews.length !== TOTAL_REVIEWS) {
  throw new Error(
    `Phase 3.2: Expected ${TOTAL_REVIEWS} reviews from Google Sheets, ` +
    `got ${allReviews.length}`
  );
}

// --- Deterministic selection: sort by review_id, take every 10th starting at offset ---
allReviews.sort((a, b) => String(a.review_id || "").localeCompare(String(b.review_id || "")));

const offset = SEED % 10;              // 42 % 10 = 2
const step = 10;                       // 1000 / 100 = 10
const selected = [];

for (let i = offset; i < allReviews.length && selected.length < SELECTED_COUNT; i += step) {
  selected.push(allReviews[i]);
}

if (selected.length !== SELECTED_COUNT) {
  throw new Error(
    `Phase 3.2: Deterministic selection produced ${selected.length} reviews, expected ${SELECTED_COUNT}`
  );
}

// --- Split selected 100 into 4 batches of 25 ---
const batches = [];
for (let i = 0; i < MAX_BATCHES; i++) {
  const start = i * BATCH_SIZE;
  const end = start + BATCH_SIZE;
  const batchReviews = selected.slice(start, end);
  const runId = `run_${SEED}`;
  const hash = require('crypto').createHash('sha256')
    .update(`${runId}:batch:${i + 1}`)
    .digest('hex').slice(0, 12);
  const batchId = `batch_${i + 1}_${hash}`;

  batches.push({
    batch_id: batchId,
    batch_index: i + 1,
    run_id: runId,
    batch_size: BATCH_SIZE,
    review_count: batchReviews.length,
    review_ids: batchReviews.map(r => r.review_id),
    reviews: batchReviews,
    selection_method: SELECTION_METHOD,
    source_dataset: "analysis_sample_1000",
    status: "pending",
    created_at: new Date().toISOString(),
  });
}

// Return one item per batch — n8n will process each through Gemini independently
return batches.map(b => ({ json: b }));
```

### Parameters
- **Operation:** Run once for all items

---

## New Node 3 — Gemini Classify Batch (Google Gemini Message a Model)

**Type:** Google Gemini (Message a Model) — SAME operation as the 25-review pilot  
**Position:** After "Generate Classification Batches"  
**Operation:** Chat / Message a Model (match your existing pilot node configuration)

### Configuration
- **Model:** Use the SAME model you selected in the existing live pilot node (DO NOT change)
- **Credential:** Reuse your existing secure Google Gemini credential (configured in n8n UI)
- **Temperature:** 0.1 (deterministic)
- **Max Output Tokens:** 4096

### System Message
Copy the full system instructions from `docs/GEMINI_CLASSIFICATION_PROMPT.md`.

### User Message (Prompt Content)

Use an n8n expression to pass the batch of 25 reviews as JSON:

```
{{ JSON.stringify($json.reviews) }}
```

### Important
- Only `cleaned_review_text` (PII-redacted) is sent to Gemini.
- Original `original_review_text` is NOT in the Google Sheets data — it is in
  the gitignored local `data/cleaned_reviews.csv` only.
- Reviews with `quote_eligible=no` are still classified but flagged.
- The Gemini response will be in `content.parts[0].text` as a JSON string.
- Do NOT expect the Gemini node to return `batch_id`, `review_ids`, or other
  batch metadata — those are in the input item (`$json.batch_id`, etc.).

---

## New Node 4 — Validate Batch Classification (Code)

**Type:** Code (JavaScript)  
**Position:** After "Gemini Classify Batch"  
**Operation:** Run once for each item

### Purpose
Parse `content.parts[0].text`, validate exactly 25 classifications,
check all expected review IDs present once, validate themes/sentiments/fee topics,
and flag questionable fee claims.

### JavaScript Code

```javascript
// Phase 3.2 — Validate Batch Classification (JavaScript)
// Input: 1 item (Gemini response + original batch data)
// Output: Validated results with errors/warnings

const VALID_THEME_IDS = ["T1", "T2", "T3", "T4", "T5"];
const VALID_SENTIMENTS = ["positive", "negative", "neutral", "unclear", "mixed"];
const VALID_FEE_TOPICS = ["brokerage", "dp_charges", "other_fee", "unspecified_fee", "none", "unclear"];
const MAX_THEMES_PER_REVIEW = 2;
const EXPECTED_BATCH_SIZE = 25;

const errors = [];
const warnings = [];
const classifiedIds = [];

// --- Parse Gemini response from content.parts[0].text ---
let geminiResults = [];
try {
  const rawText = $input.first().json.content?.parts?.[0]?.text || "";
  if (!rawText) {
    throw new Error("Missing content.parts[0].text in Gemini response");
  }
  const text = rawText.trim();
  const start = text.indexOf("[");
  const end = text.lastIndexOf("]");
  if (start === -1 || end === -1 || end < start) {
    throw new Error("No JSON array found in Gemini response text");
  }
  geminiResults = JSON.parse(text.slice(start, end + 1));
  if (!Array.isArray(geminiResults)) {
    throw new Error("Gemini response is not a JSON array");
  }
} catch (e) {
  errors.push(`Failed to parse Gemini response: ${e.message}`);
  return [{
    json: {
      valid: false,
      batch_id: $input.first().json.batch_id,
      batch_index: $input.first().json.batch_index,
      run_id: $input.first().json.run_id,
      errors,
      warnings,
      classified_review_ids: [],
      classified_count: 0,
      input_count: EXPECTED_BATCH_SIZE,
      parse_error: true,
      validated_at: new Date().toISOString(),
    },
  }];
}

// --- Get expected review IDs from this batch's input ---
const originalReviewIds = ($input.first().json.review_ids || []).map(String);
const expectedIds = new Set(originalReviewIds);

// --- Check record count ---
if (geminiResults.length !== EXPECTED_BATCH_SIZE) {
  errors.push(
    `Record count mismatch: expected ${EXPECTED_BATCH_SIZE} classifications, ` +
    `got ${geminiResults.length}`
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

  // Validate themes (empty array allowed for unclassified)
  const themes = result.themes || [];
  if (!Array.isArray(themes)) {
    errors.push(`Review ${rid}: themes is not a list`);
    continue;
  }
  if (themes.length > MAX_THEMES_PER_REVIEW) {
    errors.push(
      `Review ${rid}: ${themes.length} themes, max ${MAX_THEMES_PER_REVIEW} allowed`
    );
  }
  const invalidThemes = themes.filter(t => !VALID_THEME_IDS.includes(t));
  if (invalidThemes.length > 0) {
    errors.push(`Review ${rid}: invalid themes ${JSON.stringify(invalidThemes)}`);
  }

  // Validate sentiment (includes unclear, mixed)
  const sentiment = result.sentiment || "";
  if (!VALID_SENTIMENTS.includes(sentiment)) {
    errors.push(`Review ${rid}: invalid sentiment '${sentiment}'`);
  }

  // Validate fee topic
  const feeTopic = result.fee_topic || "none";
  if (!VALID_FEE_TOPICS.includes(feeTopic)) {
    errors.push(`Review ${rid}: invalid fee topic '${feeTopic}'`);
  }

  // Fee-topic consistency: T1 assigned ⟺ fee_topic is a specific subtype
  const isFee = themes.includes("T1");
  const hasFeeSubtype = ["brokerage", "dp_charges", "other_fee", "unspecified_fee"].includes(feeTopic);
  if (isFee !== hasFeeSubtype) {
    warnings.push(
      `Review ${rid}: questionable fee-subtype claim (T1=${isFee}, fee_topic=${feeTopic}), ` +
      "flagged for manual review"
    );
  }

  // Flag ambiguous classifications
  if (result.needs_manual_review === true) {
    warnings.push(`Review ${rid}: marked needs_manual_review by model`);
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

## New Node 5 — Store Batch Results (Code)

**Type:** Code (JavaScript)  
**Position:** After "Validate Batch Classification"  
**Operation:** Run once for each item

### Purpose
Preserve validated classifications and batch metadata. The classifications
are needed by the aggregation node.

### JavaScript Code

```javascript
// Phase 3.2 — Store Batch Results
// Input: 1 item (validated batch classification)
// Output: Stored record with classifications preserved

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
  gemini_results: validation.gemini_results,   // PRESERVED for aggregation
  validation: validation,                        // Full validation object
  questionable_fee_warnings: validation.warnings.filter(w =>
    w.includes("questionable fee-subtype")
  ),
  manual_review_warnings: validation.warnings.filter(w =>
    w.includes("marked needs_manual_review")
  ),
  validated_at: validation.validated_at,
  errors: validation.errors,
  warnings: validation.warnings,
};

return [{ json: storeRecord }];
```

### Parameters
- **Operation:** Run once for each item

---

## New Node 6 — Aggregate Classification Results (Code)

**Type:** Code (JavaScript)  
**Position:** After "Store Batch Results"  
**Operation:** Run once for all items

### Purpose
Collect all 4 validated batch results, require exactly 100 unique classified
reviews, aggregate theme frequencies, and fail if any batch is missing/failed.

### JavaScript Code

```javascript
// Phase 3.2 — Aggregate Classification Results
// Input: 4 items (one per validated batch)
// Output: Aggregated theme frequencies and run summary

const VALID_THEME_IDS = ["T1", "T2", "T3", "T4", "T5"];
const VALID_SENTIMENTS = ["positive", "negative", "neutral", "unclear", "mixed"];
const VALID_FEE_TOPICS = ["brokerage", "dp_charges", "other_fee", "unspecified_fee", "none", "unclear"];

const allResults = [];
const batchSummaries = [];
let hasFailedBatch = false;
let totalClassified = 0;
const allClassifiedIds = [];

for (const item of $input.all()) {
  const json = item.json;

  // Track batch summary
  batchSummaries.push({
    batch_id: json.batch_id,
    batch_index: json.batch_index,
    status: json.status,
    review_count: json.review_count,
    classified_count: json.classified_count,
    error_count: json.error_count,
    warning_count: json.warning_count,
  });

  // Check for failed batches
  if (json.status !== "completed" || json.error_count > 0) {
    hasFailedBatch = true;
  }

  // Collect classifications from this batch
  if (json.gemini_results && Array.isArray(json.gemini_results)) {
    for (const result of json.gemini_results) {
      allResults.push(result);
      totalClassified++;
      if (result.review_id) {
        allClassifiedIds.push(result.review_id);
      }
    }
  }
}

// --- Fail if any batch is missing or failed ---
if (hasFailedBatch) {
  throw new Error(
    "Phase 3.2 aggregation failed: one or more batches did not complete successfully. " +
    "Review batch summaries for errors."
  );
}

// --- Require exactly 100 unique classified reviews ---
const uniqueIds = new Set(allClassifiedIds);
if (uniqueIds.size !== 100) {
  throw new Error(
    `Phase 3.2 aggregation failed: expected 100 unique classified reviews, ` +
    `got ${uniqueIds.size}`
  );
}
if (allClassifiedIds.length !== uniqueIds.size) {
  throw new Error(
    "Phase 3.2 aggregation failed: duplicate review IDs found across batches"
  );
}

// --- Aggregate theme frequencies (one review at most once per theme) ---
const themeCounts = {};
VALID_THEME_IDS.forEach(tid => { themeCounts[tid] = 0; });
const sentimentCounts = {};
VALID_SENTIMENTS.forEach(s => { sentimentCounts[s] = 0; });
const feeTopicCounts = {};
VALID_FEE_TOPICS.forEach(ft => { feeTopicCounts[ft] = 0; });

let reviewsWithThemes = 0;
let reviewsWithoutThemes = 0;
const questionableFees = [];
const manualReviewFlags = [];

for (const result of allResults) {
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
  } else {
    reviewsWithoutThemes++;
  }

  if (sentimentCounts[sentiment] !== undefined) {
    sentimentCounts[sentiment]++;
  }

  if (feeTopicCounts[feeTopic] !== undefined) {
    feeTopicCounts[feeTopic]++;
  }

  // Questionable fee-subtype claims
  const isFee = themes.includes("T1");
  const hasFeeSubtype = ["brokerage", "dp_charges", "other_fee", "unspecified_fee"].includes(feeTopic);
  if (isFee !== hasFeeSubtype) {
    questionableFees.push(result.review_id);
  }

  if (result.needs_manual_review === true) {
    manualReviewFlags.push(result.review_id);
  }
}

return [{
  json: {
    run_id: $input.first().json.run_id || "unknown",
    selection_method: "systematic_step_10_seed_42",
    source_dataset: "analysis_sample_1000",
    scope: "phase_3_2_initial_test",
    total_reviews_classified: totalClassified,
    unique_reviews_classified: uniqueIds.size,
    reviews_with_themes: reviewsWithThemes,
    reviews_without_themes: reviewsWithoutThemes,
    batch_count: batchSummaries.length,
    batch_summaries: batchSummaries,
    theme_counts: themeCounts,
    sentiment_counts: sentimentCounts,
    fee_topic_counts: feeTopicCounts,
    questionable_fee_review_ids: questionableFees,
    questionable_fee_count: questionableFees.length,
    manual_review_review_ids: manualReviewFlags,
    manual_review_count: manualReviewFlags.length,
    all_classified_review_ids: sorted(allClassifiedIds),
    classification_complete: totalClassified === 100 && uniqueIds.size === 100,
    aggregated_at: new Date().toISOString(),
    scope_labels: {
      pilot_25_reviews: "separate_pilot_run",
      initial_test_100_reviews: "phase_3_2_initial_test",
      full_1000_reviews: "pending_scale_up_approval",
    },
  },
}];

function sorted(arr) {
  return [...arr].sort();
}
```

### Parameters
- **Operation:** Run once for all items

---

## Execution Control & Error Handling

| Aspect | Configuration |
|--------|--------------|
| **Max batches** | 4 (100 reviews) — hard-coded limit |
| **Gemini retries** | 3 retries with 5s/10s/20s backoff (configure in Gemini node) |
| **Failed batch** | Marked `status: "failed"`, aggregation throws error |
| **Partial results** | Never aggregated — all 4 batches must succeed |
| **Resume/retry** | Re-run from "Generate Classification Batches" — batch IDs are deterministic |

---

## Data Flow

```
Validate Review Dataset (succeeds)
        │
        ▼
Assert Validation Passed (Code)
        │
        ▼
Generate Classification Batches (Code, 4 items)
        │
    ┌───┼───┬───┬───┐
    ▼   ▼   ▼   ▼
Gemini Classify  (×4 independent calls)
    │   │   │   │
    ▼   ▼   ▼   ▼
Validate Batch   (×4 independent validations)
    │   │   │   │
    ▼   ▼   ▼   ▼
Store Batch Results (×4, classifications preserved)
        │
    ┌───┴───┴───┴───┐
    ▼
Aggregate Classification Results (Code, runs once for all 4 items)
        │
        ▼
   Final theme frequencies + scope labels
```

---

## What Must Be Manually Tested in n8n

1. **Node names:** Confirm "Get row(s) in sheet" is the exact name of your Google Sheets node
2. **Gemini credentials:** Verify your existing Gemini credential is selected
3. **Gemini model:** Confirm it matches the model used in the successful 25-review pilot
4. **Worksheet:** Confirm data is in the `analysis_sample` worksheet
5. **Batch count:** Verify Node 2 produces exactly 4 items (batches)
6. **Response parsing:** Confirm `content.parts[0].text` contains the JSON array
7. **Validation:** Run once and confirm all 4 batches pass validation
8. **Aggregation:** Confirm theme counts sum correctly and exactly 100 unique reviews
9. **Privacy:** Confirm `original_review_text` is never sent to Gemini
10. **Do NOT scale to 1,000 reviews** without explicit approval

---

## Files Reference

| File | Purpose |
|------|---------|
| `docs/GEMINI_CLASSIFICATION_PROMPT.md` | Gemini system prompt |
| `src/taxonomy.py` | Theme taxonomy (Python reference) |
| `src/batch_generator.py` | Deterministic batch generation (Python reference) |
| `src/batch_validator.py` | Batch validation + aggregation (Python reference) |
| `n8n/phase_3_2_workflow.json` | Reference workflow JSON (may need adjustment for your node types) |
| `tests/test_phase_3_2.py` | Automated local tests |
| `n8n/phase_3_2_node_instructions.md` | This file |
