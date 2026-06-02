# YouTube Comment Intelligence — Setup

## 1. Get a YouTube API Key (free)

1. Go to console.cloud.google.com
2. Create project → Enable **YouTube Data API v3**
3. Credentials → Create API Key
4. Copy the key

## 2. Get your Channel ID

Go to your YouTube channel → View Page Source → search `channelId` or use:
`https://www.youtube.com/channel/YOUR_CHANNEL_ID`

## 3. Configure

```bash
cp .env.template .env
# Edit .env — paste your keys
```

## 4. Install deps

```bash
pip install google-api-python-client openpyxl pandas anthropic
```

## 5. Run the pipeline

```bash
# Step 1 — Pull comments (200 from your 5 most recent videos)
python scripts/pull_comments.py --videos 5 --comments 200

# Step 2 — Analyze + build Excel workbook
python scripts/analyze.py

# Step 3 — Export JSON for dashboard
python scripts/export_json.py

# Step 4 — View dashboard
open site/index.html   # macOS
# or just drag site/index.html into Chrome
```

## 6. Deploy dashboard to the web

**Netlify (easiest — 30 seconds):**
1. Go to netlify.com/drop
2. Drag the `site/` folder onto the page
3. Done — you get a live URL

**Vercel:**
```bash
npm i -g vercel
cd site
vercel
```

## 7. Automate weekly refresh

Add to cron (runs every Sunday at 5pm):
```
0 17 * * 0 cd /path/to/yt-analytics && python scripts/pull_comments.py && python scripts/analyze.py && python scripts/export_json.py
```

---

## What each script does

| Script | What it does |
|---|---|
| `pull_comments.py` | Fetches comments from YouTube API → `outputs/comments_raw.csv` |
| `analyze.py` | AI analysis + builds Excel workbook → `outputs/yt_comment_insights.xlsx` |
| `export_json.py` | Converts CSV → `site/data.json` for dashboard |
| `site/index.html` | Self-contained dashboard (no build step) |
