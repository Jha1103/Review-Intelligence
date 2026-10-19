# Demo video — script and shot list

**Target: 2:50.** The brief caps it at 3:00; leave yourself margin.

Silent screen recording with on-screen captions is fine and is what the site
already claims. If you narrate, the "Say" column is your script — read it at a
normal pace, don't rush to fit.

## Setup before you hit record

```bash
cd ~/projects/review-pulse-m5
python src/analyze_results.py && python src/build_outputs.py   # must pass
python3 -m http.server 8501 -d site
```

- Browser at **http://localhost:8501**, or your deployed URL if Pages is live.
- **Close other tabs.** Hide the bookmarks bar (`Cmd+Shift+B`).
- Quit anything that shows notifications (`Do Not Disturb` on).
- Window at roughly 1440×900. Zoom at 100% (`Cmd+0`).
- Record with **QuickTime → File → New Screen Recording**, or `Cmd+Shift+5`.
  Record the **window**, not the full screen.

> Do a 20-second throwaway take first and watch it back. Check the text is
> legible and nothing private is in frame.

---

## Shot list

| # | Time | Show | Say / caption |
|---|------|------|---------------|
| 1 | 0:00–0:20 | Hero. Let the pipeline card sit on screen. | "Groww Android reviews, turned into a weekly product pulse and a customer fee explainer — delivered through an approval-gated MCP workflow." |
| 2 | 0:20–0:50 | Scroll to **Findings**. Pause on the theme bars. | "1,000 reviews, stratified from 10,000. 81% carry no substantive complaint, so that's reported as a baseline, not ranked. The top issue themes are technical issues, feature requests and support." |
| 3 | 0:50–1:20 | Scroll to the three quote cards, then the **buy vs sell** comparison. Pause here — this is the point of the project. | "The fee finding: users aren't disputing the price. One review says ₹10 on buying, ₹30 on selling. DP charges apply on the sell side only, stamp duty on the buy side only — so the sell leg costs more, and it reads as a double charge." |
| 4 | 1:20–1:45 | **Deliverables** section. Click through all four tabs. Let each render. | "Both outputs: the pulse at 249 words against a 250 limit, the explainer at six bullets with two official sources, the exact JSON appended to Google Docs, and the Gmail draft — subject line per spec, never sent." |
| 5 | 1:45–2:00 | Scenario cards. Click **Reject Path**. | "Reject first. The workflow stops at the approval gate. Zero external writes." |
| 6 | 2:00–2:35 | Click **Approve Path**. Let the canvas animate through. Scroll slightly to keep the MCP nodes in frame. | "Approve requires two conditions — the decision, and confirmation that the quotes were checked against the originals. Only then does the MCP client call append_to_doc and create_email_draft." |
| 7 | 2:35–2:50 | **MCP Inspector** panel showing the sanitised tool call. End on it. | "Each call is verified against a stored SHA-256 hash of the approved payload and claimed once, so a replay can't double-write." |

---

## Lines worth landing

If you only get three things across, these are they:

1. **The fee insight is specific.** Not "fees are confusing" — *the sell leg costs more because DP charges are sell-side only.* That's the difference between summarising reviews and actually diagnosing one.
2. **Satisfaction is a baseline, not a theme.** Leading a product pulse with "81% are happy" is useless to a PM. Say why you ranked issues separately.
3. **The gate is real.** Reject writes nothing. Approve needs two conditions. The payload is hashed and claimed once.

## Don't

- Don't show the n8n credentials screen, the Google Doc URL, or your Gmail
  account strip. Same redaction rules as `screenshots/README.md`.
- Don't narrate the code. Nobody wants a tour of `app.js`.
- Don't apologise for the sample size on camera. State it plainly — 1,000
  stratified of 10,000 — and move on. It's a defensible method.

## After recording

- Trim dead air at both ends.
- Upload to YouTube as **Unlisted**.
- Paste the URL into `site/config.js`:
  ```js
  window.DEMO_VIDEO_URL = "https://youtu.be/XXXXXXXXXXX";
  ```
- Commit, and the site's video section will embed it instead of the placeholder.
