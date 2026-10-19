# Execution evidence — capture checklist

Six screenshots proving the workflow ran, approval gated it, and the two MCP
actions landed. Follow [`docs/RUN_BOOK.md`](../docs/RUN_BOOK.md) and capture as
you go.

On macOS: `Cmd+Shift+4`, then `Space` to grab a whole window.

## The six

| # | Filename | What it must show | Why it matters |
|---|---|---|---|
| 1 | `01-approval-form.png` | The `Wait` form with both drafts and the two dropdowns | Approval is human and happens **before** any external write |
| 2 | `02-reject-no-writes.png` | Execution halted at the gate on Reject | Reject = zero external writes |
| 3 | `03-execution-success.png` | Full canvas, all nodes succeeded | The whole chain ran |
| 4 | `04-audit-table.png` | `groww_approval_audit` row: `status=approved`, `doc_status=done`, `draft_status=done` | Claim-once delivery, no double writes |
| 5 | `05-google-doc-entry.png` | The appended entry in Google Docs | Deliverable: *Notes/Doc snippet showing appended entry* |
| 6 | `06-gmail-draft.png` | The draft, **in the Drafts folder**, subject `Weekly Product Pulse + Customer Clarification — <date>`, body showing both sections | Deliverable: *Email draft screenshot* — and that it was never sent |

## Before committing — redaction

These go into a public repo. Check every image for:

- [ ] **Your Google account email / avatar** — crop or blur the Gmail and Docs
      chrome. The account strip at top-right is the usual offender.
- [ ] **The Doc URL** — the document ID is a secret; crop the address bar or
      blur the ID.
- [ ] **The Sheet URL / ID** — same.
- [ ] **n8n credential names** that embed anything private.
- [ ] **Webhook URLs and bearer tokens** — the form URL contains a webhook ID.
- [ ] **Other browser tabs, bookmarks, notifications** — crop the window
      tightly, or use a clean profile.
- [ ] **Reviewer-identifying content** — the quotes are PII-screened, but
      confirm nothing extra crept into the rendered pulse.

> The repository already leaks a Doc ID in its **git history** (see the history
> note in the README). Do not add a second copy via a screenshot.

## Wiring them into the site

The site's Execution Evidence section is currently text-only. To show the
images, drop them in here and reference them as `../screenshots/<name>.png`
from `site/`, or copy them into `site/evidence/` so a static deploy serves them.

## Naming

Keep the numeric prefixes — they set the reading order, and the run book refers
to these exact filenames.
