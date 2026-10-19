# Run book — producing the evidence for submission

One end-to-end run through the approval-gated workflow, producing a Google Docs
entry and an unsent Gmail draft that **match** the files in `outputs/`.

Do this once. It closes two deliverables: *Notes/Doc snippet showing appended
entry* and *Email draft screenshot/text*.

> **Why it matters:** if you have run this workflow before, your Google Doc and
> Gmail draft hold the *older* output — the generic fee explainer, the old
> quotes and the old `Groww — Customer Fee Explainer` subject line. Screenshots
> of that will not match the pulse you submit. Run it again.

---

## 0. Before you start

```bash
cd ~/projects/review-pulse-m5
python src/analyze_results.py && python src/build_outputs.py
```

Both must pass their limit checks. `build_outputs.py` prints the exact email
subject the run should produce — note it down to compare later.

Have ready:
- A Google Doc for the pulse log (create an empty one; copy its URL).
- The Google Sheet holding `analysis_sample` (1,000 rows).
- Your n8n Community Edition instance running.

---

## 1. Import both workflows

In n8n: **Workflows → Import from File**.

1. `n8n/Groww - Delivery Actions.json`
2. `n8n/Groww - Full 1000 Review Analysis.json`

Import *Delivery Actions* first — the analysis workflow references it by ID.

## 2. Replace the placeholders

The exports ship with placeholders on purpose; nothing real is committed. In
each node that shows a credential warning, pick your own credential:

| Placeholder | Node(s) | What to set |
|---|---|---|
| `REPLACE_WITH_YOUR_GOOGLE_SHEETS_CRED_ID` | Get row(s) in sheet, Get Reviews for Demo | Google Sheets OAuth2 |
| `REPLACE_WITH_YOUR_GEMINI_CRED_ID` | Message a model, Generate Product Pulse and Fee Explainer | Google Gemini API |
| `REPLACE_WITH_YOUR_GOOGLE_DOCS_CRED_ID` | Update a document1 | Google Docs OAuth2 |
| `REPLACE_WITH_YOUR_GMAIL_CRED_ID` | Create a draft1 | Gmail OAuth2 |
| `REPLACE_WITH_YOUR_BEARER_AUTH_CRED_ID` | MCP Server Trigger, both MCP Clients | Bearer Auth |
| `REPLACE_WITH_YOUR_SHEET_ID` | both Sheets nodes | Your `analysis_sample` sheet |
| `REPLACE_WITH_YOUR_DOC_ID` | Update a document1 | Your pulse-log Doc URL |

Create a Data Table named **`groww_approval_audit`** with text columns:
`run_id`, `payload_json`, `payload_hash`, `status`, `doc_status`,
`draft_status`, `approved_at`.

Activate **Delivery Actions** so its MCP Server Trigger is reachable.

## 3. Choose a path

**Full run (uses Gemini quota)** — Execute `Groww - Full 1000 Review Analysis`
from the manual trigger. 40 batches × 25 reviews.

**Demo run (no Gemini)** — Use the **`DEMO: Click Here (No Gemini)`** trigger.
It replays a cached validated draft through the *same* approval gate and the
*same* MCP delivery, so the evidence is genuine. Faster and free.

Either path reaches the same `Wait` node.

## 4. The approval gate  📸

n8n prints a form URL. Open it. You will see both drafts rendered.

**Capture `01-approval-form.png` here** — this is your proof that approval is
human-gated and happens *before* anything external is written.

Then, to show the Reject path first:

1. Choose **Reject** → submit. The workflow stops. Nothing is written.
   **Capture `02-reject-no-writes.png`** of the execution showing the halt.
2. Re-run, and this time set:
   - `Decision` = **Approve**
   - `Quotes checked against originals` = **Verified**

Both conditions are required; approving without verifying quotes will not pass
the `If` node.

> Verify the three quotes against your private source reviews before you tick
> Verified. That checkbox is an assertion you are making, not a formality.

## 5. Delivery  📸

After approval the workflow hashes the payload, writes the audit row, then
calls the MCP tools.

- **Capture `03-execution-success.png`** — the full canvas, all nodes green.
- **Capture `04-audit-table.png`** — the `groww_approval_audit` row showing
  `status=approved`, `doc_status=done`, `draft_status=done`.

## 6. The two artefacts  📸

- **Google Doc** — open your pulse-log Doc. The appended entry starts with
  `WEEKLY PRODUCT PULSE — <date>`.
  **Capture `05-google-doc-entry.png`.**
- **Gmail** — open **Drafts**. Subject must read
  `Weekly Product Pulse + Customer Clarification — <date>`.
  **Capture `06-gmail-draft.png`.** Make sure the body shows *both* sections.

> Confirm it sits in **Drafts**, not Sent. There is no send node in either
> workflow; this is just your own last check.

## 7. Cross-check

The Doc entry should match `outputs/doc_entry.json` and the draft should match
`outputs/email_draft.md`. If they differ, you are looking at an older run —
check the date in the entry.

## 8. Finish

Save the six PNGs into `screenshots/` using the names above, then:

```bash
python -m pytest tests/ -v
git add screenshots/ && git commit -m "Add execution evidence screenshots"
```

See `screenshots/README.md` for the checklist and redaction rules.
