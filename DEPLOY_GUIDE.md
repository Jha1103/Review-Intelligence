# Publish the Groww Review Intelligence case-study dashboard

**Architecture choice:** read-only static HTML/CSS/JavaScript on Render Static Sites. No Streamlit server, databases, live n8n connection or new tokens. Render static sites can be deployed for free within plan limits. The existing local project is preserved.

## Step 1 — Add files to your EXISTING local repo

If you placed this ZIP in `~/Downloads`:

```bash
cd "$HOME/Downloads"
unzip -o Groww_Review_Intelligence_Render_Portfolio.zip -d groww_portfolio_render_bundle
bash "$HOME/Downloads/groww_portfolio_render_bundle/install_into_existing_repo.sh"
```

The script defaults to `$HOME/projects/review-pulse-m5` and uses your Mac home folder automatically. If your project lives somewhere else, pass the path as its first argument:

```bash
bash "$HOME/Downloads/groww_portfolio_render_bundle/install_into_existing_repo.sh" "/path/to/existing/review-pulse-m5"
```

It copies only the public dashboard, case study, video guide and Render config. It **does not push or rewrite your existing Python/n8n files**, and stops if one of the destination files would be overwritten.

## Step 2 — Preview locally

```bash
cd "$HOME/projects/review-pulse-m5"
python3 -m http.server 8501 -d site
```

Open `http://localhost:8501` in your Mac browser. Stop the preview with Control-C. Port 8501 is only a convenient port number; this is *not* a Streamlit app.

## Step 3 — Publish reviewed files to GitHub

Before ANY public push, run `git status`, inspect `git log`, check tracked files for secret keys or private data, and confirm your remote is the intended repo. In particular, be sure **previous commits do not contain secrets or review-level data**. A staged-files-only commit does not sanitize earlier Git history.

```bash
cd "$HOME/projects/review-pulse-m5"
git remote -v
git status --short
git add site/ render.yaml CASE_STUDY.md VIDEO_GUIDE.md DEPLOY_GUIDE.md
git diff --cached --stat
# After reviewing the staged files AND existing Git history:
git commit -m "Add review intelligence case study dashboard" -- site render.yaml CASE_STUDY.md VIDEO_GUIDE.md DEPLOY_GUIDE.md
git push origin HEAD
```

If GitHub authentication is required, complete it using your browser or GitHub CLI. **Do not paste your GitHub token into chat.** Intended repo: <https://github.com/Jha1103/Review-Intelligence>. Check `git remote -v` before pushing.

## Step 4 — Render Static Site (free tier)

- Visit <https://dashboard.render.com> and sign in with GitHub.
- **New → Static Site**, connect the existing `Jha1103/Review-Intelligence` repository.
- Choose the pushed branch.
- **Build command:** `echo "Static portfolio — no build required"`
- **Publish directory:** `site`
- Create the Static Site. Render assigns a unique `https://...onrender.com` URL. You can also use **Blueprints → New Blueprint** to adopt the supplied `render.yaml`.
- Save the exact URL in your README and share that real URL—not a guessed URL.

Render may charge for usage beyond included monthly bandwidth/build minutes; monitor your Render usage settings. Do not deploy the entire n8n instance as a publicly accessible server.

## Step 5 — Add the video later

Record with **Shift + Command + 5**, edit/redact and upload to YouTube **Unlisted**. Open `site/config.js` and paste the YouTube link. Commit **only that changed file** and push; the site will show the video embed on the next deployment.

## What is public vs. private

Only public aggregate counts, methodology, non-identifying screenshots and final site code should be hosted. Review-level rows, raw exports, PII, source quote text, private Google links, n8n credentials, API keys, tokens and signed form URLs stay on your Mac.

## If you prefer Streamlit

Streamlit Community Cloud is another possible free option, but this site needs no server or Python packages, offers quicker static deployment, and is easier to demo. The original Python code stays in your existing repo separately.
