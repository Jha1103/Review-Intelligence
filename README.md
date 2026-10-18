# Review Intelligence — Groww Product Feedback Automation

**AI-assisted product feedback intelligence and human-approved support automation.**
An interactive portfolio case study analyzing public Groww Android reviews and prototyping an approval-gated n8n + MCP workflow that turns customer feedback into structured product insights and verified support documentation — without ever sending email autonomously.

[View the interactive demo](./site/index.html)

---

## What this project is

An independent **product management portfolio case study** that converts 8–12 weeks of public app reviews into:

1. **An AI review intelligence report** — up to 5 themes, top-3 ranked by programmatically calculated frequencies, exactly 3 verbatim quotes with real review IDs.
2. **A weekly internal product pulse** — maximum 250 words, top themes, 3 quotes, key observation, exactly 3 suggested product actions.
3. **A verified customer support fee explainer** — maximum 6 neutral factual bullets, 2 real official product URLs, `Last checked: [verified date]`.
4. **An approval-gated MCP workflow** — appends to Google Docs and creates a Gmail draft, **never sends it**.

This project is **not affiliated with or endorsed by Groww**. All data is public Google Play reviews. All automation was demonstrated locally with human approval; no customer account data or private review text is published here.

---

## Interactive demo

The public dashboard at `site/index.html` is an **interactive visual demonstration** of the real n8n + MCP automation:

- **Workflow canvas** — Google Sheets → Validate → Gemini Classification (40 batches) → Product Pulse & Fee Explainer → Human Approval → MCP Client → MCP Server Trigger → Google Docs / Gmail Draft
- **Two replay scenarios** — **Reject** (stops at approval gate, zero external writes) and **Approve** (full MCP delivery to Google Docs + unsent Gmail draft)
- **MCP Inspector panel** — sanitized tool name, request, response, and audit status for each MCP call
- **Execution timeline** — Play, Pause, Restart with per-node highlighting
- **Recorded Execution Replay** — clearly labeled as a sanitized replay of real local n8n executions, not a live connection

Open `site/index.html` locally or view the deployed site (see Deployment below).

---

## Results (1,000-review sample)

| Theme | Count | Share of classified |
|-------|-------|---------------------|
| General Satisfaction (T5) | 814 | ~81% |
| Technical Issues (T2) | 73 | ~7% |
| Feature Requests (T4) | 44 | ~4% |
| Poor Customer Support (T3) | 28 | ~3% |
| High Fees (T1) | 24 | ~2% |

- **38 reviews** received no theme (gibberish, unclear, or irrelevant)
- **25 fee-topic labels** vs. 24 fee-theme assignments — one discrepancy flagged for manual review
- **Sampling window:** August 11 – October 16, 2026
- **Collection:** 10,000 public Google Play reviews; 1,000-review stratified sample (seed=42)

These are **theme assignments on a sampled dataset**, not customer prevalence estimates or a census of all Groww users.

---

## Three product priorities

1. **Strengthen technical stability** — login failures, crashes, and functionality issues during market hours erode trust. Pair complaint themes with failure-rate and authentication funnel telemetry.
2. **Improve support responsiveness** — delayed or unresolved tickets increase customer frustration, especially when finances are involved. Measure first-response and resolution times.
3. **Make charges easier to understand** — improve brokerage and DP-charge explanations at the point of decision, anchored in official pricing rather than unverified customer amounts.

These are PM hypotheses to validate with behavioral telemetry and actual support data — not causal claims.

---

## How it works (architecture)

Python is used **only** for data collection, cleaning, and local validation/testing. n8n Cloud Community Edition + Gemini API handle AI review intelligence, report generation, human approval, and MCP publishing.

| Layer | Responsibility |
|-------|---------------|
| **Data Layer** | Scrape public Groww reviews (google-play-scraper), clean/dedupe/filter, redact PII, export CSV, load to Google Sheets |
| **AI Intelligence Layer** | n8n reads Sheets; Gemini classifies reviews into 5 fixed themes; deterministic JavaScript validation |
| **Output Layer** | Generate weekly pulse (≤250 words) and fee explainer (≤6 bullets) |
| **Human Approval** | n8n Wait form displays both outputs; explicit Approve/Reject decision; Reject = zero external writes |
| **MCP Publishing** | After approval only: `append_to_doc` → Google Docs, `create_email_draft` → Gmail draft (never sent) |
| **Persistence** | Run IDs, approval decisions, payload hashes, and action status in Google Sheets approval_log |

**Tech stack (only):** Python 3, pandas, google-play-scraper · n8n Community Edition · Google Gemini API · Google Sheets/Docs/Gmail · n8n MCP Server Trigger + MCP Client Tool · Git/GitHub · Cursor + OpenCode.

No Streamlit, Make, Zapier, or custom backend.

---

## Files in this repository

| Path | Description | Public? |
|------|-------------|---------|
| `site/index.html` | Interactive workflow demo (HTML) | ✅ |
| `site/styles.css` | Demo stylesheet | ✅ |
| `site/app.js` | Demo execution engine | ✅ |
| `site/config.js` | Config (demo video URL placeholder) | ✅ |
| `site/favicon.svg` | Site icon | ✅ |
| `render.yaml` | Render Static Site configuration | ✅ |
| `CASE_STUDY.md` | Detailed case study narrative | ✅ |
| `DEPLOY_GUIDE.md` | Render deployment instructions | ✅ |
| `VIDEO_GUIDE.md` | Demo recording guide | ✅ |
| `docs/PROJECT_PLAN.md` | Project plan and phases | ✅ |
| `docs/ARCHITECTURE.md` | Layered architecture and field mapping | ✅ |
| `docs/DECISIONS.md` | Decision log | ✅ |
| `docs/REQUIREMENTS_CHECKLIST.md` | Requirements A–L mapping | ✅ |
| `src/collect_reviews.py` | Google Play review collection | ✅ |
| `src/clean_reviews.py` | Cleaning, dedup, PII redaction | ✅ |
| `src/sample_reviews.py` | Stratified sampling (seed=42) | ✅ |
| `src/taxonomy.py` | Fixed 5-theme taxonomy | ✅ |
| `src/batch_generator.py` | Deterministic batch generation | ✅ |
| `src/batch_validator.py` | Batch validation and aggregation | ✅ |
| `tests/test_pipeline.py` | Data pipeline tests | ✅ |
| `tests/test_phase_3_2.py` | Classification pipeline tests | ✅ |
| `n8n/Groww - Full 1000 Review Analysis.json` | n8n workflow export | ❌ (contains credential references) |
| `n8n/Groww - Delivery Actions.json` | n8n delivery workflow export | ❌ (contains credential references) |
| `data/*.csv` | Review-level data (even cleaned) | ❌ (kept private) |

**Never committed:** API keys, OAuth secrets, credentials, raw review text, personal information, private document URLs, or audit payloads.

---

## How to run locally

### Data collection pipeline (Python)

```bash
cd /Users/swapniljha/projects/review-pulse-m5
source .venv/bin/activate
python -m src.collect_reviews    # Fetch raw Groww reviews
python -m src.clean_reviews      # Clean, deduplicate, redact PII, export
python -m src.sample_reviews     # Stratified analysis sample (seed=42)
python -m pytest tests/ -v       # Run all tests (83 passing)
```

### Interactive demo (static site)

```bash
cd /Users/swapniljha/projects/review-pulse-m5/site
python3 -m http.server 8765
# Open http://localhost:8765 in your browser
```

No API keys, no external connections, no n8n required to view the demo.

---

## Deployment (Render Static Site)

The site is configured as a Render **Static Site** serving the `site/` directory. See `DEPLOY_GUIDE.md` for the full step-by-step.

**Quick summary:**

1. Push this repository to GitHub (see below)
2. Visit https://dashboard.render.com and sign in with GitHub
3. **New → Static Site**, connect `Jha1103/Review-Intelligence`
4. Choose the pushed branch
5. **Build command:** `echo "Static portfolio — no build required"`
6. **Publish directory:** `site`
7. Create the Static Site — Render assigns a `https://*.onrender.com` URL

Render may charge for usage beyond included monthly bandwidth/build minutes. Monitor your Render settings.

---

## Responsible publication

- ✅ Safe for GitHub: aggregated theme counts, methodology, public static site, documentation, Python source code, tests
- ❌ Keep private: 1,000-row review files (even cleaned), original review text, phone/email/PAN, n8n credentials and workflow exports containing resource IDs or webhook paths, bearer tokens/API keys, private Google Doc/Gmail URLs, audit payloads, personal information

Screenshots and video must be reviewed frame-by-frame before publication. Do not demonstrate a live local MCP endpoint publicly.

---

## Demo video

The silent screen-recording section (`site/index.html`, `#demo`) is ready for a YouTube Unlisted video. To add one:

1. Record with macOS Shift+Command+5 (redact all secrets, names, full review text, credentials, bearer tokens, webhook URLs, private Google Doc IDs)
2. Upload to YouTube as **Unlisted**
3. Set `window.DEMO_VIDEO_URL` in `site/config.js`
4. Commit and push `site/config.js` — Render redeploys automatically

---

## GitHub repository

Existing repo: https://github.com/Jha1103/Review-Intelligence

This is not a new repository. It is the existing `review-pulse-m5` local project pushed to the existing GitHub destination.

---

*Independent portfolio project. October 2026. Not affiliated with or endorsed by Groww.*