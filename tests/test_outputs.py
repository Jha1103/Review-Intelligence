"""Guard the limits the brief imposes on the generated deliverables.

These caught a real regression: both the pulse and the cached n8n draft
came in over the 250-word limit on the first pass.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "outputs"

OFFICIAL_LINKS = [
    "https://groww.in/pricing",
    "https://groww.in/help/stocks/searchable/when-are-dp-charges-levied",
]


def read(name: str) -> str:
    path = OUT / name
    if not path.exists():
        pytest.skip(f"{name} not generated yet; run src/build_outputs.py")
    return path.read_text(encoding="utf-8")


def test_pulse_within_word_limit():
    body = re.sub(r"^#\s.*$", "", read("weekly_pulse.md"), flags=re.M)
    assert len(body.split()) <= 250


def test_fee_explainer_bullet_limit():
    bullets = [l for l in read("fee_explainer.md").splitlines() if l.startswith("- ")]
    assert 0 < len(bullets) <= 6


def test_fee_explainer_has_two_official_links_and_last_checked():
    md = read("fee_explainer.md")
    for url in OFFICIAL_LINKS:
        assert url in md
    assert re.search(r"Last checked:\*{0,2}\s*\d{4}-\d{2}-\d{2}", md)


def test_source_list_has_four_to_six_urls():
    urls = set(re.findall(r"https?://\S+", read("sources.md")))
    assert 4 <= len(urls) <= 6


def test_doc_entry_has_every_field_the_brief_requires():
    entry = json.loads(read("doc_entry.json"))
    for field in ("date", "top_themes", "weekly_pulse", "identified_fee_issue",
                  "explanation_bullets", "source_links"):
        assert field in entry, field
    assert len(entry["explanation_bullets"]) <= 6
    assert entry["source_links"] == OFFICIAL_LINKS
    assert len(entry["top_themes"]) == 3


def test_doc_entry_theme_counts_are_not_hardcoded_satisfaction():
    """T5 is a baseline, so it must never be ranked as a top issue theme."""
    entry = json.loads(read("doc_entry.json"))
    assert all(t["theme_id"] != "T5" for t in entry["top_themes"])


def test_email_subject_matches_the_brief():
    md = read("email_draft.md")
    assert re.search(
        r"Weekly Product Pulse \+ Customer Clarification — \d{4}-\d{2}-\d{2}", md
    )


def test_email_body_carries_both_deliverables():
    md = read("email_draft.md")
    assert "WEEKLY PRODUCT PULSE" in md
    assert "CUSTOMER FEE EXPLANATION" in md
    assert "NOT SENT" in md


def test_workflow_exports_carry_no_credentials_or_private_urls():
    forbidden = [
        "1wD1D38D8Pej7BN7Sva", "188TagFUnsS6axSQtWXu4", "zIajPliIebUpRaIC",
        "AGTwpKuMMbQLwDsW", "Xqi9qPVsUrfHJauY", "gvOIif2H0zYW2xXv",
        "UA1RjRbTM66Ly9NG", "instanceId",
    ]
    for wf in (ROOT / "n8n").glob("Groww*.json"):
        raw = wf.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in raw, f"{wf.name} leaks {token}"


def test_site_loads_demo_data_before_app():
    """app.js reads window.DEMO_DATA at module scope and dies without it."""
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    assert "demo-data.js" in html
    assert html.index("demo-data.js") < html.index("app.js")


def test_site_defines_every_element_id_app_js_looks_up():
    app = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    missing = [i for i in set(re.findall(r"getElementById\('([^']+)'\)", app))
               if f'id="{i}"' not in html]
    assert not missing, f"app.js references missing ids: {missing}"


def test_site_deliverables_stay_in_sync_with_outputs():
    """site/deliverables.js is generated; it must mirror outputs/."""
    js = ROOT / "site" / "deliverables.js"
    if not js.exists():
        pytest.skip("deliverables.js not generated yet; run src/build_outputs.py")
    raw = js.read_text(encoding="utf-8")
    payload = json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
    entry = json.loads(read("doc_entry.json"))

    assert payload["pulse"] == entry["weekly_pulse"]
    assert payload["feeBullets"] == entry["explanation_bullets"]
    assert payload["sourceLinks"] == entry["source_links"]
    assert payload["topThemes"] == entry["top_themes"]
    assert payload["pulseWordCount"] <= 250
    assert len(payload["feeBullets"]) <= 6
    assert payload["emailSubject"].startswith("Weekly Product Pulse + Customer Clarification")


def test_site_loads_deliverables_before_app():
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    assert "deliverables.js" in html
    assert html.index("deliverables.js") < html.index("app.js")


def test_video_url_is_actually_read_by_the_site():
    """config.js invites a URL; app.js must consume it, or it is dead config."""
    app = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
    cfg = (ROOT / "site" / "config.js").read_text(encoding="utf-8")
    assert "DEMO_VIDEO_URL" in cfg
    assert "DEMO_VIDEO_URL" in app, "config.js sets a URL app.js never reads"
    assert "youtube-nocookie" in app, "embed should use the no-cookie host"


def test_video_embed_rejects_non_https_and_unknown_hosts():
    app = (ROOT / "site" / "app.js").read_text(encoding="utf-8")
    assert "u.protocol !== 'https:'" in app
    assert "youtu.be" in app and "vimeo.com" in app


def test_site_ships_no_absolute_asset_paths():
    """GitHub Pages serves a project repo under /<repo>/, so a leading
    slash resolves to the domain root and 404s."""
    html = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
    bad = re.findall(r'(?:src|href)="/[^/"][^"]*"', html)
    assert not bad, f"absolute paths would break on a subpath deploy: {bad}"
