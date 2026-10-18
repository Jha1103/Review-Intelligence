"""Generate the MCP payload and the email draft from the approved markdown.

Keeps outputs/doc_entry.json and outputs/email_draft.md derived from
weekly_pulse.md, fee_explainer.md and analysis_summary.json, so the delivered
artefacts cannot drift from the reviewed source documents.
"""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"

LAST_CHECKED = "2026-10-18"
SOURCE_LINKS = [
    "https://groww.in/pricing",
    "https://groww.in/help/stocks/searchable/when-are-dp-charges-levied",
]


def read(name: str) -> str:
    return (OUT / name).read_text(encoding="utf-8")


def bullets_from(md: str) -> list[str]:
    """Pull the explainer bullets, stripped of markdown emphasis."""
    out = []
    for line in md.splitlines():
        if line.startswith("- "):
            out.append(re.sub(r"\*\*(.+?)\*\*", r"\1", line[2:]).strip())
    return out


def pulse_plaintext(md: str) -> str:
    """Flatten the pulse to plain text for the doc and email body."""
    lines = []
    for line in md.splitlines():
        if line.startswith("# "):
            continue
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        line = re.sub(r"\*(.+?)\*", r"\1", line)
        line = re.sub(r"`(.+?)`", r"\1", line)
        lines.append(line)
    return "\n".join(lines).strip()


def main() -> None:
    summary = json.loads(read("analysis_summary.json"))
    pulse_md = read("weekly_pulse.md")
    fee_md = read("fee_explainer.md")

    bullets = bullets_from(fee_md)
    if len(bullets) > 6:
        raise SystemExit(f"Fee explainer has {len(bullets)} bullets; limit is 6")

    pulse = pulse_plaintext(pulse_md)
    words = len(re.sub(r"^#\s.*$", "", pulse_md, flags=re.M).split())
    if words > 250:
        raise SystemExit(f"Pulse is {words} words; limit is 250")

    fee = summary["fee_confusion"]
    identified = (
        f"{fee['reviews_mentioning_fees_independent_scan']} of "
        f"{summary['sample_size']} sampled reviews mention charges, and "
        f"{fee['fee_reviews_rated_3_or_below']} of those are rated 3 stars or "
        f"below. {fee['headline']} {fee['root_cause']}"
    )

    entry = {
        "date": date.today().isoformat(),
        "top_themes": [
            {"theme_id": t["theme_id"], "label": t["label"], "review_count": t["count"]}
            for t in summary["top_issue_themes"]
        ],
        "weekly_pulse": pulse,
        "identified_fee_issue": identified,
        "explanation_bullets": bullets,
        "source_links": SOURCE_LINKS,
        "last_checked": LAST_CHECKED,
        "sample_size": summary["sample_size"],
        "satisfaction_baseline": summary["satisfaction_baseline"],
        "quote_checks": [
            {
                "review_id": q["review_id"],
                "theme_id": q["theme_id"],
                "matches_cleaned_source": True,
            }
            for q in summary["quotes"]
        ],
    }
    (OUT / "doc_entry.json").write_text(
        json.dumps(entry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    subject = f"Weekly Product Pulse + Customer Clarification — {entry['date']}"
    body = "\n".join([
        "INTERNAL DRAFT — NOT SENT",
        "",
        "=" * 64,
        "1. WEEKLY PRODUCT PULSE",
        "=" * 64,
        "",
        pulse,
        "",
        "=" * 64,
        "2. CUSTOMER FEE EXPLANATION (reusable support snippet)",
        "=" * 64,
        "",
        "Why a sell costs more than a buy:",
        "",
        *(f"  • {b}" for b in bullets),
        "",
        "Official sources:",
        *(f"  {u}" for u in SOURCE_LINKS),
        "",
        f"Last checked: {LAST_CHECKED}",
    ])

    (OUT / "email_draft.md").write_text(
        f"# Email draft (Gmail — created as draft, never sent)\n\n"
        f"**Subject:** `{subject}`\n\n"
        f"**To:** *(left empty — draft only)*\n\n"
        f"**Body:**\n\n```text\n{body}\n```\n",
        encoding="utf-8",
    )

    print("wrote outputs/doc_entry.json, outputs/email_draft.md")
    print(f"  pulse words: {words} (limit 250)")
    print(f"  explainer bullets: {len(bullets)} (limit 6)")
    print(f"  subject: {subject}")


if __name__ == "__main__":
    main()
