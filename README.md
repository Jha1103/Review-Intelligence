# Review Intelligence — Groww Product Feedback Automation

Turns public Groww Android reviews into a weekly product pulse and a customer-ready fee explainer, then delivers both through an **approval-gated MCP workflow** that appends to Google Docs and creates a Gmail draft — **never sending it**.

Independent portfolio project. Not affiliated with or endorsed by Groww.

[View the interactive demo](./site/index.html)

---

## TL;DR — the three answers a reviewer wants

| Question | Answer |
|---|---|
| **What fee issue was identified from reviews?** | Users are not disputing the *price level*. They are confused by **buy/sell charge asymmetry** — the sell leg debits more than the buy leg, which they report as a hidden or double charge. Root cause: **DP charges apply on sell transactions only**, while stamp duty applies on the buy side only. [Full detail ↓](#what-fee-issue-was-identified) |
| **Where does MCP approval happen?** | At the **`Wait` node** in `Groww - Full 1000 Review Analysis`, which renders a form requiring both *Decision = Approve* and *Quotes checked against originals = Verified*. Nothing external is written before that. [Full detail ↓](#where-mcp-approval-happens) |
| **How do I run it?** | [Jump to How to run ↓](#how-to-run) |

---

## Deliverables

All generated artefacts live in [`outputs/`](./outputs/):

| File | What it is |
|---|---|
| [`outputs/weekly_pulse.md`](./outputs/weekly_pulse.md) | Weekly product pulse — **249 words** (limit 250) |
| [`outputs/fee_explainer.md`](./outputs/fee_explainer.md) | Fee explainer — **6 bullets** (limit 6), 2 official links, `Last checked` |
| [`outputs/doc_entry.json`](./outputs/doc_entry.json) | Exact entry appended to Google Docs via MCP |
| [`outputs/email_draft.md`](./outputs/email_draft.md) | Gmail draft subject + body (never sent) |
| [`outputs/sources.md`](./outputs/sources.md) | Source list — 5 URLs, all verified reachable |
| [`outputs/analysis_summary.json`](./outputs/analysis_summary.json) | Step 1 review-intelligence output |
| [`data/reviews_sample.csv`](./data/reviews_sample.csv) | Reviews CSV sample (50 rows, sanitised) |
| [`screenshots/`](./screenshots/) | Execution evidence — see the capture checklist |

`doc_entry.json`, `email_draft.md` and `site/deliverables.js` are **generated** from the two markdown documents by `src/build_outputs.py`, so the delivered artefacts — and the site that displays them — cannot drift from the reviewed source.

**To reproduce the execution evidence** (Google Docs entry + Gmail draft), follow [`docs/RUN_BOOK.md`](./docs/RUN_BOOK.md). It is one end-to-end run through the approval gate, with the six screenshots to capture listed in [`screenshots/README.md`](./screenshots/README.md).

---

## Step 1 — Review intelligence

10,000 public Google Play reviews collected, cleaned, deduplicated and PII-redacted. A **stratified random sample of 1,000** (seed 42, stratified by review week and rating) was classified into at most 5 themes.

**Satisfaction baseline:** 814 / 1,000 (81%) carry no substantive complaint, tracking a 768/1,000 five-star skew.

**Top 3 issue themes** (General Satisfaction is reported as a baseline, not ranked as a product issue):

| Rank | Theme | Reviews |
|---|---|---|
| 1 | Technical Issues (T2) | 73 |
| 2 | Feature Requests (T4) | 44 |
| 3 | Poor Customer Support (T3) | 28 |
| — | High Fees (T1) — *fee focus* | 24 |

38 reviews received no theme (gibberish or unclear). Sampling window: 11 Aug – 16 Oct 2026.

> Counts are theme assignments **within this sample**, not estimates of the Groww customer base. A review may carry up to 2 themes, so theme counts sum above the number of classified reviews.

**Known discrepancy, flagged not reconciled:** fee-topic labels total **25** while the T1 theme count is **24** — one review carries a fee topic without the theme. An independent multilingual keyword scan (`src/analyze_results.py`, no API key needed) finds **25** fee-mentioning reviews, corroborating the fee-topic total and the one-review gap.

---

## What fee issue was identified

**The confusion:** users see a larger deduction on selling than on buying the same stock and report it as a hidden or double charge.

Evidence from the sample — 19 of 25 fee-mentioning reviews are rated 3★ or below:

- `01d9c2da` (1★) — *"…kharine pr 10 aur bechne pr 30"* — ₹10 on buying, ₹30 on selling
- `e6e92ebe` (1★) — *"its take very high charge in buy and sell **two times take charges**"*
- `f858c1d9` (3★) — *"aapka deduction tax **one time kaatna chahie** sale Karen ya buy"*

**The actual answer:** DP (depository) charges are levied only when shares *leave* your demat account, so they apply on **sell transactions only** — per sell transaction, not per share. Stamp duty applies on the **buy side only**. The sell leg therefore normally costs more than a comparable buy leg. It is one charge per leg, not the same charge applied twice.

Full customer-facing wording: [`outputs/fee_explainer.md`](./outputs/fee_explainer.md).

---

## Where MCP approval happens

The approval gate is a **two-condition human checkpoint**, and no external system is touched before it passes.

```
Sheets → Validate → Gemini (40 × 25) → Validate & Count → Pulse + Fee Explainer
      → Normalise and Check Draft
      → [ Wait  ← ■ HUMAN APPROVAL FORM ]
      → If (Approve AND Verified)
      → Verify Quotes and Build Payload → Hash (SHA-256) → Audit Table
      → MCP Client → MCP Server Trigger → append_to_doc / create_email_draft
```

1. **`Wait` node** (`Groww - Full 1000 Review Analysis`) renders a form showing both drafts and requires **two** answers:
   - `Decision` = **Approve**
   - `Quotes checked against originals` = **Verified**
2. **`If` node** proceeds only when *both* conditions hold. Reject ⇒ zero external writes.
3. **`Verify Quotes and Build Payload`** re-checks each quote is quote-eligible, identifier-free and verbatim in the pulse, then builds the payload. Theme counts are read from the analysis node — never hardcoded.
4. **SHA-256 hash** of the payload is stored with the approval in a persistent audit table.
5. **`Groww - Delivery Actions`** (the MCP tool workflow) independently re-hashes the incoming payload and refuses to act unless the hash matches a persisted `approved` record. Each action is **claimed once** (`pending → in_progress → done`) so a replayed call cannot double-write.

**Approval cannot be bypassed by the model.** The MCP tools accept only `run_id` + `payload_hash` + `payload_json`; the delivery workflow verifies all three against the audit table before any Google Docs or Gmail call.

Gmail is **`resource: draft`** only. No send node exists in either workflow.

---

## Architecture

| Layer | Responsibility | Technology |
|---|---|---|
| Data | Scrape, clean, dedupe, PII-redact, stratified sample | Python 3, pandas, google-play-scraper |
| AI | Classify 1,000 reviews into 5 themes; validate counts | n8n CE, Gemini API, JavaScript |
| Output | Pulse (≤250 words) and fee explainer (≤6 bullets) | n8n + Gemini |
| Approval | Two-condition human gate; Reject = zero external writes | n8n `Wait` form |
| MCP | `append_to_doc` → Google Docs; `create_email_draft` → Gmail draft | n8n MCP Server Trigger + MCP Client |
| Integrity | Run IDs, SHA-256 payload hashes, claim-once action status | n8n Data Table |

No Streamlit, Make, Zapier, or custom backend.

---

## How to run

### Data pipeline and outputs (Python, no API key needed)

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python -m src.collect_reviews    # fetch raw reviews (needs network)
python -m src.clean_reviews      # clean, dedupe, redact PII
python -m src.sample_reviews     # stratified 1,000-row sample

python src/analyze_results.py    # -> outputs/analysis_summary.json
python src/build_outputs.py      # -> outputs/*, site/deliverables.js
python -m pytest tests/ -v
```

`analyze_results.py` and `build_outputs.py` enforce the brief's limits and **fail loudly** rather than truncating: the pulse must be ≤250 words, the explainer ≤6 bullets, and the two official source links must be unaltered.

### Interactive demo (static site)

```bash
python3 -m http.server 8501 -d site
```

Then open http://localhost:8501.

### n8n workflows

Import both files from [`n8n/`](./n8n/). They ship with **placeholder credential IDs** (`REPLACE_WITH_YOUR_*`) and placeholder Google Sheet/Doc IDs — set your own before running. `Groww - Full 1000 Review Analysis` includes a **`DEMO: Click Here (No Gemini)`** trigger that replays a cached validated draft, so the approval gate and MCP delivery can be demonstrated without burning Gemini quota.

---

## Deployment

### GitHub Pages (simplest — no new account)

`.github/workflows/pages.yml` publishes `site/` on every push to `main` that
touches it. Enable it once:

**repo → Settings → Pages → Source: "GitHub Actions"**

The site then lives at `https://jha1103.github.io/Review-Intelligence/`. The
workflow fails the build if an absolute asset path creeps in, because Pages
serves a project repo under a subpath where a leading slash would 404.

### Render Static Site

`render.yaml` is also configured: static runtime, no build step, publish
directory `site`. Connect the repo in Render and deploy.

---

## Demo video

[`docs/VIDEO_SCRIPT.md`](./docs/VIDEO_SCRIPT.md) has a timed shot list for a
2:50 recording, plus setup and redaction steps.

Once recorded, paste the URL into `site/config.js`:

```js
window.DEMO_VIDEO_URL = "https://youtu.be/XXXXXXXXXXX";
```

The page embeds it automatically — YouTube, Vimeo, or a direct `.mp4`/`.webm`/
`.mov` over https — and drops the placeholder. Leave it empty and the
placeholder stays.

---

## Files

| Path | Description | Committed? |
|---|---|---|
| `outputs/` | Generated deliverables (pulse, explainer, doc entry, email draft, sources) | ✅ |
| `site/` | Interactive workflow demo (HTML/CSS/JS) | ✅ |
| `src/` | Collection, cleaning, sampling, analysis and output-build code | ✅ |
| `tests/` | pytest suite | ✅ |
| `data/analysis_sample.csv` | Stratified 1,000-row sample, PII-redacted | ✅ |
| `data/reviews_sample.csv` | 50-row sanitised CSV sample | ✅ |
| `data/reviews_for_sheets.csv` | Sanitised export for Google Sheets | ✅ |
| `data/classification_results.json` | Recorded classifier run — single source of truth for theme counts | ✅ |
| `data/sampling_report.json` | Sampling methodology report | ✅ |
| `n8n/*.json` | Workflow exports, placeholder credentials only | ✅ |
| `docs/` | Architecture, prompt, run book and video script | ✅ |
| `screenshots/` | Execution evidence images + capture checklist | ✅ |
| `site/deliverables.js` | Generated; mirrors `outputs/` for the site | ✅ |
| `.github/workflows/pages.yml` | GitHub Pages deploy | ✅ |
| `render.yaml` | Render Static Site blueprint | ✅ |
| `data/raw_reviews.csv`, `data/cleaned_reviews.csv` | Pre-redaction review text | ❌ gitignored |
| `config/config.local.json`, `.env`, `state/` | Credentials and operational state | ❌ gitignored |

---

## Security

- No API keys, OAuth secrets or tokens are committed. `config/config.example.json` is a template only.
- Workflow exports carry **placeholder** credential IDs and placeholder Sheet/Doc IDs; the n8n `instanceId` fingerprint is stripped.
- Pre-redaction review text (`raw_reviews.csv`, `cleaned_reviews.csv`) is gitignored. Committed CSVs are PII-redacted and carry no `original_review_text` column.
- Quotes are published only when `quote_eligible=yes`, `pii_redacted=no`, and the text passes an identifier check — enforced in code, then confirmed by a human at the approval gate.
- The public demo site is read-only and connects to no live service.

> **History note:** earlier commits contain a real Google Doc ID and a real Sheets credential ID. These are sanitised in the current files, but remain in git history. If that document is sensitive, rotate the credential and unshare the doc — removing it from history requires a rewrite (`git filter-repo`) and a force-push.

---

*Independent portfolio project. Not affiliated with or endorsed by Groww.*
