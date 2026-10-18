# Milestone 5 — Architecture (n8n-first)

## 1. Layered data flow

```text
┌─────────────────────────────────────────────────────────────┐
│ LAYER 1 — DATA (Python + Pandas, local)                     │
│  google-play-scraper → Groww public reviews                 │
│  12-week window (configurable)                              │
│  Pagination, retries, error handling                        │
│  Fields: reviewId, at (date), score→rating, content,        │
│          userName, appVersion, source provenance            │
│  → raw_reviews.csv                                          │
│  → clean: dedup by reviewId, drop empty/invalid,            │
│          PII redaction (no PII in exclusion log)            │
│  → cleaned_reviews.csv, reviews_sample.csv                  │
│  → data_quality_report.json (counts)                        │
│  → upload to Google Sheets                                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ LAYER 2 — AI INTELLIGENCE (self-hosted n8n CE + Gemini)     │
│  n8n reads Google Sheets                                    │
│  Gemini: discover ≤5 themes, classify reviews,              │
│          extract 3 verbatim quotes, detect recurring        │
│          fee issue                                          │
│  n8n Code nodes: deterministic frequencies, evidence        │
│          validation, formatting rules                       │
│  → themes.json, quotes, fee-issue evidence                  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ LAYER 3 — OUTPUT (n8n + Gemini)                             │
│  Weekly product pulse: ≤250 words, top themes, 3 quotes,    │
│          key observation, exactly 3 product actions         │
│  Fee explainer: ≤6 neutral bullets, 2 official URLs,        │
│          Last checked: verified date                        │
│  → pulse.md, fee_explainer.md                               │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ LAYER 4 — HUMAN APPROVAL (n8n CE form)                      │
│  Display BOTH complete outputs                              │
│  Explicit Approve / Reject decision                         │
│  Reject → zero external writes                              │
│  → approval decision persisted                              │
└─────────────────────────────────────────────────────────────┘
                              │  Approve only
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ LAYER 5 — MCP PUBLISHING (n8n MCP Client + Server Trigger)  │
│  append_to_doc  → structured dated entry to Google Doc      │
│  create_email_draft → Gmail draft (NEVER send)              │
│  Both tools independently verify authorization              │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ LAYER 6 — PERSISTENCE (n8n Data Tables or Google Sheets)    │
│  Run IDs, approval decisions, payload hashes,               │
│  action status; retry + duplicate-write handling            │
└─────────────────────────────────────────────────────────────┘
```

## 2. Layer responsibilities

| Layer | Responsibility | Technology |
|-------|---------------|------------|
| Data Layer | Collect genuine Groww reviews; clean/dedupe/filter; export CSVs; load to Google Sheets | Python 3, pandas, google-play-scraper, Google Sheets API |
| AI Intelligence Layer | Theme discovery (≤5), review classification, 3 verbatim quotes, recurring fee-issue detection | n8n CE (self-hosted), Gemini API |
| Deterministic Validation | Frequency counting (JavaScript), evidence validation, formatting rules | n8n Code nodes |
| Output Layer | Pulse (≤250 words), fee explainer (≤6 bullets, 2 URLs, Last checked) | n8n + Gemini |
| Human Approval | Form displays both outputs; explicit Approve/Reject; Reject = no writes | n8n CE form |
| MCP Layer | `append_to_doc`, `create_email_draft` after approval only; no email send | n8n MCP Client Tool + MCP Server Trigger |
| Persistence | Run IDs, approval decisions, payload hashes, action status; retry/dedup | n8n Data Tables or Google Sheets |

## 3. Field mapping (google-play-scraper → schema)

google-play-scraper returns review objects. Verified fields to preserve:

| Source field | Mapped to | Notes |
|--------------|-----------|-------|
| `reviewId` | `review_id` | Original public review ID (preserved exactly) |
| `at` | `review_date` | Review date (ISO-8601) |
| `score` | `rating` | 1–5 star rating mapped from `score` |
| `content` | `review_text` | Exact original review text |
| `content` | `cleaned_text` | PII-redacted copy for AI processing |
| `userName` | `reviewer_name` | Provenance (may be redacted if PII) |
| `appVersion` | `app_version` | Provenance |
| — | `source_url` | Google Play app page URL (no per-review URL assumed) |
| — | `source` | `"google_play"` |
| — | `collected_at` | Run timestamp |

**No per-review public URLs are assumed or fabricated.** Source provenance is the Google Play app page URL plus `reviewId`.

## 4. PII handling
- PII (emails, phones, PAN/Aadhaar-like patterns, account numbers) is detected and redacted in `cleaned_text` **before** any external AI processing.
- Original `review_text` is preserved securely in `cleaned_reviews.csv` (not sent to Gemini).
- Exclusion log records reasons **without** exposing sensitive information.
- Verbatim quotes are used only when they contain no sensitive PII.
- No raw sensitive information is logged.

## 5. State model (cloud persistence, not local JSON)
Persisted in n8n Data Tables or Google Sheets:

```json
{
  "runId": "groww-20260115-001",
  "product": "Groww",
  "windowWeeks": 12,
  "runDate": "2026-01-15",
  "counts": { "fetched": 240, "dateFiltered": 210, "duplicates": 8, "excluded": 12, "cleaned": 190 },
  "approvalState": "pending|approved|rejected",
  "approvedAt": null,
  "payloadHash": "sha256-of-outputs",
  "actions": {
    "append_to_doc": { "status": "not_run|done|skipped", "docId": "...", "at": null },
    "create_email_draft": { "status": "not_run|done|skipped", "draftId": "...", "at": null }
  },
  "retryCount": 0,
  "completedAt": null
}
```

n8n workflow reads this store before any MCP call; refuses unless `approvalState == "approved"` and the action status is `not_run`.

## 6. Local vs self-hosted n8n CE boundary

**Built locally (this repo):** Python collection/cleaning code, tests, config template, docs, sample data.

**Configured manually in self-hosted n8n CE (by user):**
- Self-hosted n8n CE instance at `http://localhost:5678` (Docker Compose, `~/n8n-groww/`)
- Initial owner account created via browser (no placeholder password in compose)
- Google Sheets connection (store cleaned dataset).
- Gemini API credential in n8n.
- n8n Form for human approval.
- MCP Server Trigger tools `append_to_doc` and `create_email_draft` registered and authenticated.
- MCP Client Tool in the workflow.
- Existing Google Doc ID and Gmail destination (integration phase only).
- n8n Data Tables or Google Sheets for persistence.

No code in this repository writes to Google or Gmail directly; all external writes happen through n8n MCP after approval.

## 7. Security rules
- No API keys, OAuth secrets, or tokens committed. `config/config.example.json` is a template only.
- No local CLI approval for the final workflow; approval is an n8n CE form step.
- No local JSON files as the authorization source for cloud MCP tools.
- No invented review data, output data, source URLs, screenshots, or execution results.