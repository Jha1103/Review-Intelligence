# Record a ~3-minute demo on your Mac

This is designed for one take. Record **only after concealing names, email addresses, full review text, credentials, bearer tokens, webhook URLs, private Google Doc IDs and account details**. You can use redacted still screenshots rather than live n8n when necessary.

## Recording

1. Open the public dashboard locally (or Render URL after deployment) and prepare **redacted** screenshots of your n8n approval and audit results. Close unnecessary tabs and notifications.
2. Press **Shift + Command + 5** on macOS. Choose **Record Selected Portion**, then **Options → Microphone** if you want live narration. Record your browser window, not your full desktop.
3. End using the menu-bar Stop button. Review the recording for secrets or personal data **before** uploading anywhere.
4. Upload video to **YouTube → Unlisted**. An unlisted link is accessible to anyone who has it; it is not private. Use 720p/1080p MP4 if available. Prefer this over committing a large MP4 into GitHub.
5. In your existing local repo open `site/config.js`, set `window.DEMO_VIDEO_URL = "https://youtu.be/YOUR_VIDEO_ID";`, then commit and push `site/config.js`. Render redeploys after the push.

## Three-minute narration / shot list

| Time | Show | What to say |
| --- | --- | --- |
| 0:00–0:25 | Dashboard hero and scope | “I built an AI-assisted product feedback pipeline for Groww Android reviews. I collected 10,000 public reviews and analyzed a cleaned sample of 1,000.” |
| 0:25–0:55 | Theme chart; click Tech and Fees | “Forty batches were validated; key issue themes include technical problems, feature requests, support, and fee concerns. Counts describe a sampled set, not all customers.” |
| 0:55–1:25 | Priorities | “I prioritized technical reliability first, support responsiveness second, and fee communication third, explaining the product trade-offs.” |
| 1:25–1:55 | **Redacted screenshot** of n8n workflow and approval form | “Gemini drafts the pulse and fee explainer, then a human must review both. Reject prevents delivery; Approve is audit-tracked.” |
| 1:55–2:20 | Redacted aggregate-only screenshot of Google Doc + Gmail unsent draft | “The approved local run appended a structured report to Docs and created a Gmail draft, never sending the message.” |
| 2:20–2:40 | Build log / Cursor and OpenCode | “I built and debugged the analysis in Cursor, used OpenCode for coding and integration work, and corrected the automation based on tests.” |
| 2:40–3:00 | Summary and GitHub link | “The public dashboard intentionally has no live credentials or customer-level review data. Source, architecture, and methodology are in GitHub.” |

## Evidence checklist

- [ ] 1,000 sampled review result counts on dashboard
- [ ] Reject execution reaching False branch; no action
- [ ] Approved audit showing Docs done / Draft done, **crop out payload hash and JSON**
- [ ] Google Doc aggregate report, **crop out all account details and private URL**
- [ ] Gmail draft subject and unsent status, **crop out recipient/account/email**
- [ ] Cursor/OpenCode usage explained factually
- [ ] Recording contains no secrets, personal information, raw review rows or unsafe hyperlinks

The dashboard works before the video exists; you can deploy it first and add the Unlisted video afterward.
