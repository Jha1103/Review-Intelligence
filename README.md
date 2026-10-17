# Milestone 5 — AI Product Feedback Intelligence and Support Automation

**Product:** Groww (confirmed)
**Google Play package ID:** `com.nextbillion.groww`
**Country:** `in` | **Language:** `en` | **Review window:** Last 12 weeks (configurable)

**Goal:** Convert 8–12 weeks of public Groww app reviews into an AI review intelligence report, a weekly product pulse (≤250 words), a verified support fee explainer (≤6 bullets), and an approval-gated MCP workflow that appends to Google Docs and creates a Gmail draft (never sends).

## Architecture (n8n-first)

Python is used **only** for data collection, cleaning, and local validation/testing. n8n Cloud + Gemini handle AI review intelligence, report generation, human approval, and MCP publishing.

| Layer | Responsibility | Runs where |
|-------|---------------|------------|
| Data Layer | Scrape Groww reviews, clean/dedupe/filter, export CSV, load to Google Sheets | Python + Pandas (local) |
| AI Intelligence Layer | Theme discovery (≤5), classification, 3 verbatim quotes, fee-issue detection | n8n Cloud + Gemini |
| Deterministic Validation | Frequencies (JavaScript), evidence, formatting rules | n8n Code nodes |
| Output Layer | Pulse (≤250 words), fee explainer (≤6 bullets) | n8n + Gemini |
| Human Approval | n8n form displays both outputs; explicit Approve/Reject | n8n Cloud form |
| MCP Layer | `append_to_doc` + `create_email_draft` after approval only; no send | n8n MCP Client → MCP Server Trigger |
| Persistence | Run IDs, approval decisions, payload hashes, action status | n8n Data Tables or Google Sheets |

## Status
Planning documents updated (n8n-first, Groww confirmed). Phase 1 (data collection) not yet implemented. No scraping or external API calls made.

## Folder structure
See `docs/PROJECT_PLAN.md` (§4) for the proposed tree and `docs/ARCHITECTURE.md` for the layered data flow.

## Docs
- `docs/PROJECT_PLAN.md` — objective, phases, success criteria
- `docs/ARCHITECTURE.md` — layered architecture, field mapping, PII, state model
- `docs/REQUIREMENTS_CHECKLIST.md` — requirements A–L mapped to verification
- `docs/DECISIONS.md` — decision log (Groww confirmed, n8n-first)

## Planned deliverables
`README.md`, `sources.md` (4–6 official URLs), `data/reviews_sample.csv`, `outputs/pulse.md`, `outputs/fee_explainer.md`, `n8n/review-pulse-workflow.json`, `screenshots/`, `demo_script.md` (3 minutes).

## Security
No API keys, OAuth secrets, or tokens are committed. Configure credentials in n8n Cloud and environment variables only. No local CLI approval for the final workflow. No local JSON files as authorization source for cloud MCP tools.