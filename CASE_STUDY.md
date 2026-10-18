# Milestone 5 — AI Product Feedback Intelligence and Customer Support Automation

## What this project is

An independent **product management portfolio case study** analyzing public Groww Android reviews and prototyping a human-approved automation pipeline. The public [dashboard](./site/index.html) is read-only; the actual n8n workflows were run locally.

This project is not affiliated with or endorsed by Groww.

## Problem and user need

App reviews contain signals about technical reliability, support quality, fee clarity, requested features and satisfaction, but manually reading thousands of comments is slow. The PM goal was to create a repeatable, defensible review-to-decision process, and to draft support content without allowing a model to send messages autonomously.

## Data and methodology

- **Collection:** 10,000 distinct public Google Play review records, approximately 11 Aug–16 Oct 2026.
- **Analysis sample:** 1,000 cleaned sampled reviews.
- **Classification:** 40 Gemini batches of 25 reviews each; review IDs and response cardinality validated in n8n.
- **Themes:** T1 High Fees, T2 Technical Issues, T3 Poor Customer Support, T4 Feature Requests, T5 General Satisfaction. Each review can have zero to two themes. Theme counts therefore overlap.
- **Manual review:** 38 reviews unclassified; one fee-topic vs. fee-theme mismatch flagged; three quotations were matched to cleaned review entries, but source-original verification should not be claimed unless performed independently.
- **Scope:** Results describe this specific public-review sample, not a population estimate for all Groww customers.

## Results

| Theme | Count in 1,000-review sample |
| --- | ---: |
| General Satisfaction (T5) | 814 |
| Technical Issues (T2) | 73 |
| Feature Requests (T4) | 44 |
| Poor Customer Support (T3) | 28 |
| High Fees (T1) | 24 |

Other signals: 38 unclassified; fee-topic label totals 25 (14 brokerage, 11 unspecified fee) versus 24 T1 assignments. Count differences were flagged rather than silently reconciled.

## Three product priorities

1. **Stability and sign-in recovery** — core functionality interruptions can prevent action during market hours.
2. **Support responsiveness** — unresolved tickets and poor communications can weaken trust in a financial service.
3. **Pricing clarity** — address fee confusion by surfacing accurate context, including brokerage versus DP charges.

These are PM hypotheses/priorities to validate with behavioral telemetry and actual support data—not a quantified causal claim.

## Human-in-the-loop automation

1. Read cleaned sample from Google Sheets; validate counts and IDs.
2. Classify multilingual reviews using Gemini and a fixed taxonomy.
3. Generate weekly-format product pulse and six-bullet fee explainer.
4. Display both drafts in an n8n form with Approve / Reject. Reject does not enter delivery.
5. Track approval, payload hashes and delivery action status in a persistent n8n Data Table; invoke MCP tools to append to Google Docs and create **unsent** Gmail drafts.

**Local demo result, 18 Oct 2026:** Reject branch test succeeded. One approved delivery record ended with both `doc_status=done` and `draft_status=done` in the local audit. Google Doc insertion was visually confirmed, and the Gmail-only recovery reported a draft created; Gmail draft visual confirmation should be captured in demo evidence. This does not make the public dashboard a live or hosted n8n service.

## How Cursor and OpenCode were used

- **Cursor:** local code editing and iteration on Python review-processing code, tests and documentation.
- **OpenCode:** AI-assisted code generation/debugging, workflow integration investigation and local automation scripts. Suggestions required human review; some generated n8n integrations needed manual correction and live testing.
- **n8n:** executable pipeline, approval form, MCP tools and audit.
- **Gemini:** multilingual review classification and text drafts; it did not autonomously approve or send emails.
- **Google Sheets/Docs/Gmail:** source table and approved draft destinations.
- **GitHub/Render:** public code and read-only static portfolio hosting.

## Responsible-publication boundary

**Safe for GitHub:** this summary, aggregated theme counts, methodology, generated public static site, redacted diagrams and screenshots.

**Keep private:** 1,000-row review files (even cleaned ones), original review text, phone numbers/email/PAN, copied quotations not cleared for external use, n8n credentials and full workflow exports containing resource IDs or webhook paths, any bearer token/API key, Google Doc/Gmail URLs containing private identifiers, audit payloads, personal accounts and private user information.

Screenshots and video must be reviewed frame by frame before publication. Do not demonstrate a live local MCP endpoint publicly.

## Official fee references

- <https://groww.in/pricing>
- <https://groww.in/help/stocks/sx-reports/what-are-the-different-charges-mentioned-in-the-report>

Last checked in the research workflow: 18 October 2026. Refer to current official pages before providing real customer advice.
