# Execution evidence — verified MCP run

Run `groww_36`, 2026-10-19. Taken from the n8n SQLite database, not from a
screenshot, so every line below is checkable against the instance.

## Execution chain

| # | Workflow | Mode | Status | Meaning |
|---|---|---|---|---|
| 36 | Groww - Full 1000 Review Analysis | `manual` | success | Demo trigger → approval gate → payload built and hashed |
| 37 | Groww - Delivery Actions | `integrated` | success | MCP tool call 1 — `append_to_doc` |
| 38 | Groww - Full 1000 Review Analysis | `webhook` | success | MCP Server Trigger response |
| 39 | Groww - Delivery Actions | `integrated` | success | MCP tool call 2 — `create_email_draft` |
| 40 | Groww - Full 1000 Review Analysis | `webhook` | success | MCP Server Trigger response |

`mode=integrated` is the proof the delivery workflow ran **as an MCP tool
invoked by the client**, not by hand. Executed directly it refuses: its
`Check Tool Inputs` node throws `Forbidden operation` when no approved
`operation` is supplied.

## Approval record

From the `groww_approval_audit` data table:

| Field | Value |
|---|---|
| `run_id` | `groww_36` |
| `payload_hash` | `26de8548e8067fd25f7279cd552be08b4cf61bcbc063c67e3367e14aa2f1f9f4` |
| `status` | `approved` |
| `doc_status` | `pending` → `done` |
| `draft_status` | `pending` → `done` |
| `approved_at` | 2026-10-19T03:41:33.916Z |
| completed | 2026-10-19T03:41:39.028Z |

Approval was recorded at 03:41:33 and both actions completed by 03:41:39 —
**nothing external was written before the approval row existed.**

## Per-action verification

| | Execution #37 | Execution #39 |
|---|---|---|
| Operation | `append_to_doc` | `create_email_draft` |
| `run_id` present | yes | yes |
| Payload hash matched | yes | yes |
| Passed `Verify Persisted Approval` | yes | yes |
| Action node | `Update a document1` | `Create a draft1` |
| Completion node | `Mark append_to_doc Done` | `Mark create_email_draft Done` |
| API response | Google Docs `documentId` | Gmail `threadId` |

Each tool re-hashed the incoming payload and compared it against the persisted
approval before acting. Each action was claimed once (`pending → in_progress →
done`), so a replayed MCP call cannot double-write.

## Payload delivered

- Top themes: Technical Issues (73), Feature Requests (44), Poor Customer Support (28)
- Satisfaction baseline reported separately: T5, 814
- Three quotes, each with `matches_cleaned_source: true`
- Fee issue: buy/sell charge asymmetry, DP charges sell-side only
- 6 explanation bullets, 2 official source links, `last_checked: 2026-10-18`
- `sample_size: 1000`

## Gmail

The Gmail node is configured `resource: draft`. Neither workflow contains a
send node. Execution #39 returned a `threadId` for a created draft; no message
was sent.
