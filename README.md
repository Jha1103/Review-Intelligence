# Review Intelligence — Groww Product Feedback Automation

AI-assisted product feedback intelligence and human-approved support automation. Converts public Groww Android reviews into structured product insights and verified support documentation — with an approval-gated MCP workflow that appends to Google Docs and creates a Gmail draft, **never sending it**.

Not affiliated with or endorsed by Groww.

[View the interactive demo](./site/index.html)

## What the project does

Collects public Google Play reviews for Groww and converts them into:

- **AI review intelligence report** — up to 5 themes, top-3 ranked by frequency, verbatim quotes with real review IDs
- **Weekly product pulse** — ≤250 words, top themes, 3 quotes, key observation, 3 product actions
- **Customer support fee explainer** — ≤6 neutral factual bullets, 2 official URLs, `Last checked` date
- **Approval-gated MCP workflow** — human Approve/Reject gate; on Approve, appends to Google Docs and creates a Gmail draft (never sends)

## Interactive demo

The [`site/`](./site/) directory is a self-contained HTML/CSS/JavaScript replay of the real n8n + MCP workflow. Open `site/index.html` locally to:

- Step through the workflow canvas: Google Sheets → Validate → Gemini (40 batches) → Pulse & Fee Explainer → Human Approval → MCP Client → MCP Server Trigger → Google Docs / Gmail Draft
- Toggle between **Reject** (zero external writes) and **Approve** (full MCP delivery) scenarios
- Inspect MCP tool calls in the inspector panel (sanitized requests/responses)

No API keys, external connections, or n8n instance required to view the demo.

## Results (1,000-review sample)

| Theme | Count | Share |
|-------|-------|-------|
| General Satisfaction (T5) | 814 | ~81% |
| Technical Issues (T2) | 73 | ~7% |
| Feature Requests (T4) | 44 | ~4% |
| Poor Customer Support (T3) | 28 | ~3% |
| High Fees (T1) | 24 | ~2% |

38 reviews received no theme (gibberish/unclear). Sampling window: Aug 11 – Oct 16, 2026. These are theme assignments on a stratified sample, not estimates of all Groww users.

## Architecture & tech stack

| Layer | Responsibility | Technology |
|-------|---------------|------------|
| Data | Scrape, clean, dedupe, PII-redact, export CSV | Python 3, pandas, google-play-scraper |
| AI | Classify reviews into 5 themes; validate counts | n8n CE, Gemini API, JavaScript |
| Output | Generate pulse (≤250 words) and fee explainer (≤6 bullets) | n8n + Gemini |
| Approval | Human Approve/Reject gate; Reject = zero external writes | n8n Wait form |
| MCP | `append_to_doc` → Google Docs; `create_email_draft` → Gmail draft (never sent) | n8n MCP Client + Server Trigger |
| Persistence | Run IDs, approval state, payload hashes, action status | Google Sheets approval_log |

**Tech stack (only):** Python 3, pandas, google-play-scraper · n8n Community Edition · Google Gemini API · Google Sheets/Docs/Gmail · n8n MCP Server Trigger + MCP Client Tool · Git/GitHub · Cursor + OpenCode

No Streamlit, Make, Zapier, or custom backend.

## Files in this repository

| Path | Description | Public? |
|------|-------------|---------|
| `site/index.html` | Interactive workflow demo | ✅ |
| `site/styles.css` | Demo stylesheet | ✅ |
| `site/app.js` | Demo execution engine | ✅ |
| `site/config.js` | Config (video URL placeholder) | ✅ |
| `site/favicon.svg` | Site icon | ✅ |
| `site/demo-data.js` | Sanitized demo data | ✅ |
| `render.yaml` | Render Static Site config | ✅ |
| `requirements.txt` | Python dependencies | ✅ |
| `config/config.example.json` | Config template (no secrets) | ✅ |
| `src/` | Python collection/cleaning/sampling code | ✅ |
| `tests/` | pytest test suite | ✅ |
| `docs/ARCHITECTURE.md` | Layered architecture and field mapping | ✅ |
| `docs/GEMINI_CLASSIFICATION_PROMPT.md` | Gemini system prompt | ✅ |
| `n8n/Groww - Full 1000 Review Analysis.json` | n8n workflow export | ⚠️ placeholder credentials |
| `n8n/Groww - Delivery Actions.json` | n8n delivery workflow export | ⚠️ placeholder credentials |
| `data/*.csv` | Review-level data | ❌ (kept private) |

**Never committed:** API keys, OAuth secrets, credentials, raw review text, personal information, private document URLs, audit payloads.

## How to run locally

### Data pipeline (Python)

```bash
source .venv/bin/activate
python -m src.collect_reviews   # Fetch raw Groww reviews
python -m src.clean_reviews     # Clean, deduplicate, redact PII
python -m src.sample_reviews    # Stratified analysis sample
python -m pytest tests/ -v      # Run tests
```

### Interactive demo (static site)

```bash
cd site
python3 -m http.server 8765
# Open http://localhost:8765
```

## Deployment (Render Static Site)

`render.yaml` configures a Render Static Site serving `site/`:

- **Build command:** `echo "Static portfolio — no build required"`
- **Publish directory:** `site`

Connect the GitHub repo in Render, select the branch, and deploy.

## Security

- No credentials, tokens, or secrets are committed. `config/config.example.json` is a template only.
- Review-level data files (`data/*.csv`) are gitignored and kept private.
- n8n workflow JSONs use placeholder credential IDs only.
- The public dashboard is read-only and connects to no live services.

*Independent portfolio project. Not affiliated with or endorsed by Groww.*
