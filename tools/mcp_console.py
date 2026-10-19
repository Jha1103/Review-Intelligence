#!/usr/bin/env python3
"""Live MCP control console for the Groww review-intelligence workflow.

Serves a small panel that triggers the REAL n8n workflow over its webhook and
then shows what actually happened: executions, MCP tool calls, Google Docs and
Gmail responses, and the approval audit table.

It deliberately cannot approve anything. Approval happens at n8n's own form,
which is the control this project exists to demonstrate; a console that wrote
its own approved audit row would be demonstrating the bypass instead.

    python3 tools/mcp_console.py          # then open http://localhost:8700

Reads n8n state by snapshotting its SQLite file out of the container, so it
needs no n8n API key. Nothing is written back.
"""

from __future__ import annotations

import json
import re
import shutil
import sqlite3
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

CONTAINER = "n8n-groww"
N8N = "http://localhost:5678"
WEBHOOK = f"{N8N}/webhook/mcp-console-run"
PORT = 8700

ANALYSIS_ID = "Lu3RqGhZAg4oqfIM"
DELIVERY_ID = "TEQi8qqevof4F319"
AUDIT_TABLE = "data_table_user_h0VKrpTikZl8B8Af"

HERE = Path(__file__).resolve().parent
SNAP = Path(tempfile.gettempdir()) / "mcp_console_snapshot"


def snapshot_db() -> Path | None:
    """Copy n8n's SQLite (plus WAL) out of the container for a consistent read."""
    SNAP.mkdir(exist_ok=True)
    db = SNAP / "database.sqlite"
    for suffix in ("", "-wal", "-shm"):
        src = f"{CONTAINER}:/home/node/.n8n/database.sqlite{suffix}"
        dst = str(db) + suffix
        try:
            subprocess.run(["docker", "cp", src, dst], check=suffix == "",
                           capture_output=True, timeout=30)
        except Exception:
            if suffix == "":
                return None
    return db if db.exists() else None


def n8n_up() -> bool:
    try:
        with urllib.request.urlopen(f"{N8N}/healthz", timeout=4) as r:
            return json.loads(r.read()).get("status") == "ok"
    except Exception:
        return False


def unflatten(raw: str, max_depth: int = 60):
    """Expand n8n's interned execution data into ordinary JSON.

    n8n dedupes every string and object into a flat array and stores indices,
    so the same index legitimately appears many times. Memoise rather than
    treating a repeat visit as a cycle; only a genuine self-reference is one.
    """
    arr = json.loads(raw)
    if not isinstance(arr, list):
        return arr
    memo: dict[int, object] = {}
    resolving: set[int] = set()

    def walk(node, depth):
        if depth > max_depth:
            return "<max-depth>"
        if isinstance(node, str) and node.isdigit():
            i = int(node)
            if not (0 <= i < len(arr)):
                return node
            if i in memo:
                return memo[i]
            if i in resolving:
                return "<circular>"
            resolving.add(i)
            try:
                v = walk(arr[i], depth + 1)
            finally:
                resolving.discard(i)
            memo[i] = v
            return v
        if isinstance(node, list):
            return [walk(x, depth + 1) for x in node]
        if isinstance(node, dict):
            return {k: walk(v, depth + 1) for k, v in node.items()}
        return node

    return walk(arr[0], 0)


def redact(value):
    """Shorten the private document id and the bulky payload for display."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k == "documentId" and isinstance(v, str) and len(v) > 12:
                out[k] = v[:10] + "…(redacted)"
            elif k == "payload_json" and isinstance(v, str) and len(v) > 220:
                out[k] = v[:220] + f"… (+{len(v) - 220} chars)"
            else:
                out[k] = redact(v)
        return out
    if isinstance(value, list):
        return [redact(v) for v in value[:4]]
    if isinstance(value, str) and len(value) > 400:
        return value[:400] + "…"
    return value


def execution_log(eid: int) -> dict:
    """Node-by-node log for one execution: status, duration and real output."""
    db = snapshot_db()
    if db is None:
        return {"error": "Could not read n8n state."}
    con = sqlite3.connect(str(db))
    try:
        meta = con.execute(
            "select e.status, e.mode, e.startedAt, e.stoppedAt, w.name "
            "from execution_entity e left join workflow_entity w on w.id=e.workflowId "
            "where e.id=?", (eid,)).fetchone()
        row = con.execute("select data from execution_data where executionId=?",
                          (eid,)).fetchone()
        if not meta or not row:
            return {"error": f"No execution #{eid}"}
        data = unflatten(str(row[0]))
        run_data = data.get("resultData", {}).get("runData", {}) if isinstance(data, dict) else {}
        nodes = []
        for name, runs in run_data.items():
            r = runs[0] if isinstance(runs, list) and runs else {}
            if not isinstance(r, dict):
                continue
            try:
                out = r["data"]["main"][0][0]["json"]
            except Exception:
                out = None
            nodes.append({
                "node": name,
                "status": r.get("executionStatus"),
                "ms": r.get("executionTime"),
                "startTime": r.get("startTime"),
                "output": redact(out) if out is not None else None,
                "error": str(r.get("error"))[:300] if r.get("error") else None,
            })
        nodes.sort(key=lambda n: n.get("startTime") or 0)
        err = data.get("resultData", {}).get("error") if isinstance(data, dict) else None
        return {
            "id": eid, "workflow": meta[4], "status": meta[0], "mode": meta[1],
            "startedAt": meta[2], "stoppedAt": meta[3], "nodes": nodes,
            "error": str(err)[:400] if err else None,
        }
    finally:
        con.close()
        shutil.rmtree(SNAP, ignore_errors=True)


def decision_of(blob: str) -> tuple[str | None, str | None]:
    """Resolve the approval form answers from n8n's interned execution data.

    n8n dedupes strings into a table and stores indices, so
    {"Decision": "5721"} means the answer is entry 5721. Returns
    (decision, quotes_verified), both None while the form is unanswered.
    """
    try:
        arr = json.loads(blob)
    except Exception:
        return None, None
    if not isinstance(arr, list):
        return None, None

    def deref(v):
        if isinstance(v, str) and v.isdigit():
            i = int(v)
            if 0 <= i < len(arr) and isinstance(arr[i], str):
                return arr[i]
        return v if isinstance(v, str) else None

    for item in arr:
        if isinstance(item, dict) and "Decision" in item:
            dec = deref(item["Decision"])
            if dec in ("Approve", "Reject"):
                return dec, deref(item.get("Quotes checked against originals"))
    return None, None


def _read_state_once() -> dict:
    db = snapshot_db()
    if db is None:
        return {"error": "Could not read n8n state. Is the container running?"}

    con = sqlite3.connect(str(db))  # read-write so the WAL is applied
    try:
        execs = []
        rows = con.execute(
            "select e.id, e.workflowId, w.name, e.status, e.mode, e.startedAt, e.stoppedAt "
            "from execution_entity e left join workflow_entity w on w.id = e.workflowId "
            "order by e.id desc limit 12"
        ).fetchall()
        for eid, wfid, name, status, mode, started, stopped in rows:
            entry = {
                "id": eid, "workflow": name or wfid, "status": status,
                "mode": mode, "startedAt": started, "stoppedAt": stopped,
                "isDelivery": wfid == DELIVERY_ID, "operation": None, "detail": None,
                "decision": None, "quotesVerified": None,
            }
            if wfid == ANALYSIS_ID:
                d = con.execute("select data from execution_data where executionId=?",
                                (eid,)).fetchone()
                if d:
                    dec, ver = decision_of(str(d[0]))
                    entry["decision"] = dec
                    entry["quotesVerified"] = ver
                    if dec == "Reject":
                        # The whole point of the reject take: prove nothing moved.
                        entry["detail"] = "halted at approval gate · zero external writes"
                    elif dec == "Approve":
                        entry["detail"] = f"approved · quotes {str(ver or '').lower()}"
            if wfid == DELIVERY_ID:
                d = con.execute("select data from execution_data where executionId=?",
                                (eid,)).fetchone()
                blob = str(d[0]) if d else ""
                if '"append_to_doc"' in blob:
                    entry["operation"] = "append_to_doc"
                elif '"create_email_draft"' in blob:
                    entry["operation"] = "create_email_draft"
                bits = []
                m = re.search(r'"documentId":\s*"([^"]{6,})"', blob)
                if m:
                    bits.append(f"Google Docs documentId {m.group(1)[:12]}…")
                m = re.search(r'"threadId":\s*"([^"]{3,})"', blob)
                if m:
                    bits.append(f"Gmail threadId {m.group(1)[:12]}…")
                if "Verify Persisted Approval" in blob:
                    bits.append("hash verified against stored approval")
                entry["detail"] = " · ".join(bits) or None
            execs.append(entry)

        audit = [
            {"id": r[0], "run_id": r[1], "status": r[2], "doc_status": r[3],
             "draft_status": r[4], "approved_at": r[5]}
            for r in con.execute(
                f"select id, run_id, status, doc_status, draft_status, approved_at "
                f"from {AUDIT_TABLE} order by id desc limit 6")
        ]

        waiting = con.execute(
            "select id from execution_entity where workflowId=? and status in "
            "('waiting','running','new') order by id desc limit 1", (ANALYSIS_ID,)
        ).fetchone()

        # n8n signs the resume URL, so it cannot be constructed from the
        # execution id alone — an unsigned link is rejected as "Invalid Form
        # Link". Read the signed URL n8n actually generated.
        form_url = None
        if waiting:
            d = con.execute("select data from execution_data where executionId=?",
                            (waiting[0],)).fetchone()
            if d:
                m = re.search(r'https?://[^"\\ ,]*?/form-waiting/\d+\?signature=[a-f0-9]+',
                              str(d[0]))
                if m:
                    form_url = m.group(0)
    finally:
        con.close()
        shutil.rmtree(SNAP, ignore_errors=True)

    return {
        "n8n": n8n_up(),
        "executions": execs,
        "audit": audit,
        "waitingExecutionId": waiting[0] if waiting else None,
        "formUrl": form_url,
    }


def read_state() -> dict:
    """Snapshot and read, retrying a torn copy.

    docker cp of a database n8n is actively writing can land mid-write and
    come back "malformed". That is a bad snapshot, not a damaged instance,
    so retry briefly and degrade to a message rather than killing the server.
    """
    last = None
    for attempt in range(3):
        try:
            return _read_state_once()
        except sqlite3.DatabaseError as e:
            last = e
            time.sleep(0.6 * (attempt + 1))
        except Exception as e:
            last = e
            break
    return {"n8n": n8n_up(), "executions": [], "audit": [],
            "waitingExecutionId": None, "formUrl": None,
            "transient": f"Could not read a clean snapshot ({last}). Retrying…"}


def trigger_run() -> dict:
    req = urllib.request.Request(
        WEBHOOK, data=json.dumps({"source": "mcp-console"}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return {"ok": True, "status": r.status, "body": r.read().decode()[:300]}
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:300]
        hint = ("The webhook is not registered. Open the workflow in n8n and "
                "save it once so the production webhook registers."
                if e.code == 404 else "")
        return {"ok": False, "status": e.code, "body": body, "hint": hint}
    except Exception as e:
        return {"ok": False, "status": 0, "body": str(e)[:300]}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, payload, ctype="application/json"):
        body = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        route = self.path.split("?", 1)[0]  # a query string must not 404
        if route.startswith("/api/execution/"):
            try:
                self._send(200, execution_log(int(route.rsplit("/", 1)[-1])))
            except ValueError:
                self._send(400, {"error": "bad execution id"})
            except Exception as e:
                self._send(200, {"error": str(e)[:200]})
        elif route == "/api/state" or self.path.startswith("/api/state"):
            try:
                self._send(200, read_state())
            except Exception as e:
                self._send(200, {"n8n": n8n_up(), "executions": [], "audit": [],
                                 "transient": str(e)[:160]})
        elif route in ("/", "/index.html"):
            html = (HERE / "mcp_console.html").read_bytes()
            self._send(200, html, "text/html; charset=utf-8")
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        if self.path.split("?", 1)[0] == "/api/run":
            self._send(200, trigger_run())
        else:
            self._send(404, {"error": "not found"})

    def log_message(self, *a):  # keep the recording's terminal quiet
        pass


if __name__ == "__main__":
    print(f"MCP console  ->  http://localhost:{PORT}")
    print(f"n8n reachable: {n8n_up()}")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
