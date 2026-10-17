# Milestone 5 — Decision Log (n8n-first)

| # | Decision | Rationale | Status |
|---|----------|-----------|--------|
| D1 | Product is **Groww** (confirmed). Package ID `com.nextbillion.groww`, country `in`, language `en`, 12-week review window. | User confirmed the product; no longer `[PRODUCT_NAME]` TBD. | Approved |
| D2 | Architecture is **n8n-first**. Python is only for data collection, cleaning, and local validation/testing. n8n Cloud + Gemini handle AI intelligence, report generation, human approval, and MCP publishing. | Explicit user requirement. | Approved |
| D3 | Google Sheets stores the cleaned review dataset; n8n reads from Sheets. | Requirement: cleaned data persisted in a shared, n8n-accessible store. | Approved |
| D4 | Theme discovery via Gemini; frequency ranking done programmatically with JavaScript in n8n Code nodes. Python + Pandas are for local data processing only. | Requirement C: programmatically calculated frequencies, auditable. | Approved |
| D5 | Exactly 3 verbatim quotes, each bound to a real `reviewId`; quotes contain no PII. | Requirement C + G (PII handling). | Approved |
| D6 | Fee-issue branch stops and requests manual review when <2 reviews support the issue. | Requirement D: never invent a fee issue. | Approved |
| D7 | Human approval via n8n Cloud form displaying BOTH outputs; explicit Approve/Reject; Reject = zero external writes. No local CLI approval in final workflow. | Requirements H–K; prevents unapproved writes. | Approved |
| D8 | MCP tools `append_to_doc` and `create_email_draft` invoked only after approval; each independently verifies authorization; never send email. | Requirements I–J. | Approved |
| D9 | Persistence in n8n Data Tables or Google Sheets (run IDs, approval decisions, payload hashes, action status). No local JSON files as authorization source for cloud MCP tools. | Requirement K; cloud-authorized state. | Approved |
| D10 | PII redacted before external AI processing; exclusion log contains no PII; verbatim quotes only when PII-free. | Requirement G (PII handling). | Approved |
| D11 | No credentials, API keys, or secrets committed. `config/config.example.json` is a template only. Google Doc ID and Gmail credentials not requested until integration phase. | Working rules; least privilege. | Approved |
| D12 | `.gitignore` excludes private raw data (`data/raw_reviews.csv`, `data/cleaned_reviews.csv`, `data/data_quality_report.json`), `state/`, `.env`; allows sanitized `data/reviews_sample.csv`, final Markdown reports (`outputs/`), docs, screenshots, and reviewed n8n workflow exports to be committed. | Separation of private/operational vs committable deliverables. | Approved |
| D13 | `score` from google-play-scraper maps to `rating`; no per-review public URLs assumed or fabricated. Source provenance is the Google Play app page URL + `reviewId`. | Accurate field mapping; no invention. | Approved |

### Open items needing user input (integration phase only)
1. n8n Cloud instance URL and credentials.
2. Gemini API key (supplied by user, never committed).
3. Google Sheets connection details for storing cleaned data.
4. Target existing Google Doc ID and Gmail draft destination (integration phase).
5. Confirmation of supported Gemini model before implementation.
6. n8n Data Tables or Google Sheets choice for persistence store.

### Product configuration (confirmed — no longer open)
- Product: Groww
- Google Play package ID: `com.nextbillion.groww`
- Country: `in`, Language: `en`
- Review window: 12 weeks (configurable)
- Google Play URL: https://play.google.com/store/apps/details?id=com.nextbillion.groww
- Official pricing: https://groww.in/pricing
- Official support: https://groww.in/help/stocks