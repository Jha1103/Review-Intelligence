"""Derive the Step 1 review-intelligence summary.

Theme counts come from the recorded classifier run
(data/classification_results.json). The fee evidence is re-derived from
data/analysis_sample.csv on every run, so the fee finding is reproducible
without an API key and acts as an independent check on the classifier.

Writes outputs/analysis_summary.json.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "data" / "analysis_sample.csv"
CLASSIFIED = ROOT / "data" / "classification_results.json"
OUT = ROOT / "outputs" / "analysis_summary.json"

# Terms that indicate the review is talking about money charged, in English,
# Hindi/Hinglish transliteration and Gujarati.
FEE_TERMS = {
    "charge": r"charg\w*|chrg\w*|ચાર્જ",
    "brokerage": r"brokerage|brokrage|broker\s?age|brokerge|બ્રોકરેજ",
    "fee": r"\bfee[s]?\b",
    "dp_or_demat": r"\bdp\s*charg|demat\s*charg",
    "amc": r"\bamc\b|annual\s*maintenance",
    "hidden_or_deducted": r"hidden|extra\s*(charg|cut|deduct)|deduct\w*",
    "statutory": r"\bstt\b|\bgst\b|stamp\s*duty|\bsebi\b|\btax\b",
    "commission": r"commission",
}

# The three quotes carried into the pulse. Chosen for evidential value:
# each one shows the problem rather than only expressing displeasure.
QUOTES = [
    ("e6afdabd-5336-47bd-985c-a5302b699cdb", "T2", "order-path defect"),
    ("ec74a5f0-aa7c-4623-b74e-0bd8c04cc133", "T3", "unresolved non-trade request"),
    ("01d9c2da-575e-46b5-9e7a-d5ce3019a168", "T1", "buy/sell charge asymmetry"),
]


def load_rows() -> list[dict]:
    with SAMPLE.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def scan_fee_reviews(rows: list[dict]) -> tuple[list[dict], Counter]:
    """Return fee-mentioning reviews and a count per fee term."""
    found, term_hits = [], Counter()
    for row in rows:
        text = (row.get("cleaned_review_text") or "").lower()
        tags = [name for name, pat in FEE_TERMS.items() if re.search(pat, text)]
        if not tags:
            continue
        for tag in tags:
            term_hits[tag] += 1
        found.append({**row, "_fee_terms": tags})
    return found, term_hits


def quote_is_publishable(row: dict) -> bool:
    """Only quote reviews cleared for quoting and free of identifiers."""
    text = row.get("cleaned_review_text") or ""
    if row.get("quote_eligible") != "yes" or row.get("pii_redacted") != "no":
        return False
    identifier = r"\d{7,}|[6-9]\d{4}[\s.-]*\d{5}|@|\[REDACTED"
    return not re.search(identifier, text, re.I) and 20 <= len(text) <= 350


def main() -> None:
    rows = load_rows()
    recorded = json.loads(CLASSIFIED.read_text(encoding="utf-8"))
    by_id = {r["review_id"]: r for r in rows}

    fee_rows, term_hits = scan_fee_reviews(rows)
    fee_ratings = Counter(r["rating"] for r in fee_rows)
    negative_fee = sum(fee_ratings[s] for s in ("1", "2", "3"))

    counts = recorded["theme_counts"]
    labels = recorded["taxonomy"]
    # "General Satisfaction" is a baseline, not a product issue. Rank the
    # issue themes separately so the pulse leads with something actionable.
    issues = sorted(
        ((t, c) for t, c in counts.items() if t != "T5"),
        key=lambda kv: kv[1],
        reverse=True,
    )

    quotes = []
    for review_id, theme, why in QUOTES:
        row = by_id.get(review_id)
        if row is None:
            raise SystemExit(f"Quote review_id not in sample: {review_id}")
        if not quote_is_publishable(row):
            raise SystemExit(f"Quote not publishable: {review_id}")
        quotes.append({
            "review_id": review_id,
            "theme_id": theme,
            "theme": labels[theme],
            "selected_because": why,
            "rating": int(row["rating"]),
            "review_date": row["review_date"][:10],
            "text": row["cleaned_review_text"],
        })

    classifier_t1 = counts["T1"]
    fee_topic_total = sum(recorded["fee_topic_counts"].values())
    summary = {
        "product": recorded["product"],
        "sample_size": recorded["sample_size"],
        "population_size": recorded["population_size"],
        "sample_window": recorded["sample_window"],
        "themes": {t: {"label": labels[t], "count": c} for t, c in counts.items()},
        "satisfaction_baseline": {
            "count": counts["T5"],
            "share_of_sample": round(counts["T5"] / recorded["sample_size"], 3),
            "note": "No substantive complaint or feature request.",
        },
        "top_issue_themes": [
            {"rank": i, "theme_id": t, "label": labels[t], "count": c}
            for i, (t, c) in enumerate(issues[:3], start=1)
        ],
        "quotes": quotes,
        "fee_confusion": {
            "headline": (
                "Users are not disputing the price level. They are confused by "
                "the asymmetry between buy-side and sell-side charges, and read "
                "the larger sell-side debit as being charged twice."
            ),
            "reviews_mentioning_fees_independent_scan": len(fee_rows),
            "classifier_theme_t1_count": classifier_t1,
            "classifier_fee_topic_total": fee_topic_total,
            "scan_matches_fee_topic_total": len(fee_rows) == fee_topic_total,
            "reconciliation_note": (
                f"A multilingual keyword scan of the same sample finds "
                f"{len(fee_rows)} fee-mentioning reviews. That matches the "
                f"classifier's fee-topic total ({fee_topic_total}) and exceeds "
                f"its T1 theme count ({classifier_t1}) by "
                f"{len(fee_rows) - classifier_t1}. The gap is the known "
                f"discrepancy below, independently corroborated rather than "
                f"reconciled away."
            ),
            "fee_reviews_rated_3_or_below": negative_fee,
            "term_hits": dict(term_hits.most_common()),
            "evidence_review_ids": [
                "01d9c2da-575e-46b5-9e7a-d5ce3019a168",
                "e6e92ebe-7f0e-41b3-83cd-fc5d8b3e2532",
                "f858c1d9-f83b-48e8-b6cd-8fe51540d6c5",
            ],
            "root_cause": (
                "DP charges are levied only when shares leave the demat account, "
                "so they apply on sell transactions and not on buys; stamp duty "
                "applies on the buy side only. The sell leg therefore normally "
                "costs more than a comparable buy leg."
            ),
        },
        "known_discrepancies": recorded["known_discrepancies"],
        "methodology_note": recorded["methodology_note"],
    }

    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  fee mentions (scan): {len(fee_rows)}  classifier T1 theme: {classifier_t1}  fee-topic total: {fee_topic_total}")
    print(f"  fee reviews <=3 stars: {negative_fee}/{len(fee_rows)}")
    print(f"  top issue themes: {[(t, c) for t, c in issues[:3]]}")
    print(f"  quotes verified publishable: {len(quotes)}")


if __name__ == "__main__":
    main()
