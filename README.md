# Milestone 5 — AI Product Feedback Intelligence and Support Automation

**Product:** Groww (confirmed)
**Google Play package ID:** `com.nextbillion.groww`
**Country:** `in` | **Language:** `en` | **Review window:** Last 12 weeks (configurable)

**Goal:** Convert 8–12 weeks of public Groww app reviews into an AI review intelligence report, a weekly product pulse (≤250 words), a verified support fee explainer (≤6 bullets), and an approval-gated MCP workflow that appends to Google Docs and creates a Gmail draft (never sends).

## Phase 1 Status — COMPLETE

Python data collection, cleaning, and validation pipeline is implemented and tested. Real Groww reviews have been collected and cleaned.

### Phase 1 Results

| Metric | Value |
|--------|-------|
| Total reviews fetched | 10,000 |
| Final cleaned reviews | 10,000 |
| Date range | 2026-08-11 to 2026-10-16 |
| Rating distribution | 1★:1,052 / 2★:162 / 3★:278 / 4★:823 / 5★:7,685 |
| PII redactions | 4 reviews |
| Quote-eligible reviews | 9,996 |
| Collection limit | Stopped at 10,000-review safety cap (pagination did not end naturally) |
| Tests | 29 passed, 0 failed |

### Data Files

| File | Description | Committable? |
|------|-------------|--------------|
| `data/raw_reviews.csv` | Raw scraped reviews (gitignored — may contain PII) | No |
| `data/cleaned_reviews.csv` | Cleaned reviews with original text (gitignored — may contain PII) | No |
| `data/reviews_for_sheets.csv` | Privacy-safe export for Google Sheets (no original text) | Yes |
| `data/reviews_sample.csv` | Sanitized 50-row sample | Yes |
| `data/analysis_sample.csv` | Stratified 1,000-row sample for Gemini prototyping | Yes |
| `data/sampling_report.json` | Sampling methodology and distributions | Yes |
| `data/data_quality_report.json` | Collection and cleaning quality metrics (gitignored) | No |

## Architecture (n8n-first)

Python is used **only** for data collection, cleaning, and local validation/testing. n8n Cloud + Gemini handle AI review intelligence, report generation, human approval, and MCP publishing.

| Layer | Responsibility | Runs where |
|-------|---------------|------------|
| Data Layer | Scrape Groww reviews, clean/dedupe/filter, export CSV | Python + Pandas (local) |
| AI Intelligence Layer | Theme discovery (≤5), classification, 3 verbatim quotes, fee-issue detection | n8n Cloud + Gemini |
| Deterministic Validation | Frequencies (JavaScript), evidence, formatting rules | n8n Code nodes |
| Output Layer | Pulse (≤250 words), fee explainer (≤6 bullets) | n8n + Gemini |
| Human Approval | n8n form displays both outputs; explicit Approve/Reject | n8n Cloud form |
| MCP Layer | `append_to_doc` + `create_email_draft` after approval only; no send | n8n MCP Client → MCP Server Trigger |
| Persistence | Run IDs, approval decisions, payload hashes, action status | n8n Data Tables or Google Sheets |

## Folder structure
See `docs/PROJECT_PLAN.md` (§4) for the proposed tree and `docs/ARCHITECTURE.md` for the layered data flow.

## Docs
- `docs/PROJECT_PLAN.md` — objective, phases, success criteria
- `docs/ARCHITECTURE.md` — layered architecture, field mapping, PII, state model
- `docs/REQUIREMENTS_CHECKLIST.md` — requirements A–L mapped to verification
- `docs/DECISIONS.md` — decision log (Groww confirmed, n8n-first)

## Planned deliverables
`README.md`, `sources.md` (4–6 official URLs), `data/reviews_sample.csv`, `data/analysis_sample.csv`, `data/sampling_report.json`, `outputs/pulse.md`, `outputs/fee_explainer.md`, `n8n/review-pulse-workflow.json`, `screenshots/`, `demo_script.md` (3 minutes).

## How to run Phase 1

```bash
cd /Users/swapniljha/projects/review-pulse-m5
source .venv/bin/activate
python -m src.collect_reviews    # Step 1: fetch raw Groww reviews
python -m src.clean_reviews      # Step 2: clean, deduplicate, redact PII, export
python -m src.sample_reviews     # Step 3: stratified analysis sample
python -m pytest tests/ -v       # Step 4: run all tests
```

Override defaults via environment variables:
```bash
GROWW_WEEKS_BACK=8 GROWW_MAX_REVIEWS=500 python -m src.collect_reviews
```

## Security
No API keys, OAuth secrets, or tokens are committed. Configure credentials in n8n Cloud and environment variables only. No local CLI approval for the final workflow. No local JSON files as authorization source for cloud MCP tools. Private raw data (`cleaned_reviews.csv` with original text) is never committed to GitHub.