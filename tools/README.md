# MCP Console

A small control panel for recording the workflow actually working — trigger a
real run, watch n8n execute it, see the MCP tool calls land.

```bash
python3 tools/mcp_console.py     # then open http://localhost:8700
```

Requires the `n8n-groww` container running. No dependencies beyond the Python
standard library, and no n8n API key — it reads state by snapshotting n8n's
SQLite file out of the container.

## What it does

| Step | Action |
|---|---|
| 1 | **Run workflow** → `POST /webhook/mcp-console-run`, the real n8n webhook |
| 2 | **Open approval form** → n8n's own form, where a human approves |
| 3 | MCP delivery appears live: `append_to_doc`, `create_email_draft` |

Below that: every execution with its mode and status, and the live
`groww_approval_audit` table showing `pending → done`.

`mode=integrated` is the thing to point at while recording — it means the
delivery workflow ran **as an MCP tool call**, not by hand.

## What it deliberately cannot do

It cannot approve. Approval happens at n8n's form, and the console has no
path to write an approved audit row. A console that could approve would be
demonstrating the bypass of the control this project exists to show.

## If "Run workflow" returns 404

The production webhook is not registered. Open the workflow in n8n and save
it once, which registers it.
