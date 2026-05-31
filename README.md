# Solarlux Lead Intelligence MVP

A web dashboard that scrapes planned German construction projects from **BauNetz.de**, uses **Claude Haiku** to extract structured lead data, scores each lead for Solarlux sales relevance, and displays the results in a filterable Streamlit interface.

## File structure

```
solarlux-mvp/
  app.py            # Streamlit dashboard
  scraper.py        # Fetch BauNetz.de project list + detail pages
  extractor.py      # Claude Haiku extraction → structured JSON
  scorer.py         # Transparent 0–100 relevance scoring
  db.py             # SQLite read/write
  pipeline.py       # Wires scrape → extract → score → store
  seed_data.json    # Pre-scraped leads (demo fallback — never empty UI)
  requirements.txt
  .streamlit/
    config.toml     # Theme (Solarlux red)
```

---

## Run locally

### 1. Install dependencies
```bash
pip install -r requirements.txt
```
Or with uv (recommended):
```bash
uv sync
```

### 2. Set API key
```bash
# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# macOS / Linux
export ANTHROPIC_API_KEY="sk-ant-..."
```

### 3. Launch
```bash
streamlit run app.py
# or with uv:
uv run streamlit run app.py
```

Open **http://localhost:8501** — the dashboard loads instantly from `seed_data.json`.  
Click **"Live-Scraping starten"** in the sidebar to fetch fresh leads.

---

## Deploy to Streamlit Community Cloud (share.streamlit.io)

### Step 1 — Push to GitHub

```bash
# From inside solarlux-mvp/
git init
git add app.py scraper.py extractor.py scorer.py db.py pipeline.py \
        seed_data.json requirements.txt README.md \
        .streamlit/config.toml .gitignore
git commit -m "Initial commit: Solarlux Lead Intelligence MVP"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/solarlux-mvp.git
git push -u origin main
```

> Create the repo first at https://github.com/new (name: `solarlux-mvp`, private is fine).

### Step 2 — Deploy on Streamlit Community Cloud

1. Go to **https://share.streamlit.io** and sign in with your GitHub account.
2. Click **"New app"**.
3. Select:
   - **Repository:** `YOUR_USERNAME/solarlux-mvp`
   - **Branch:** `main`
   - **Main file path:** `app.py`
4. Click **"Deploy"**.

### Step 3 — Add the API key to Streamlit Secrets

1. In your deployed app's dashboard, click **"⋮" → "Settings" → "Secrets"**.
2. Paste the following:

```toml
ANTHROPIC_API_KEY = "sk-ant-YOUR_KEY_HERE"
```

3. Click **"Save"**. The app restarts automatically.

### Result
Your app is now live at a URL like:  
`https://YOUR_USERNAME-solarlux-mvp-app-XXXXX.streamlit.app`

The dashboard loads immediately from `seed_data.json` even if BauNetz.de is unavailable.  
Live scraping works whenever the API key is set and the site is reachable.

---

## Scoring logic (shown in sidebar)

| Criterion | Points |
|---|---|
| Project type: MFH / Hotel / Büro / Mixed-use | +45 |
| Project type: Umbau / Sanierung / Schule | +25 |
| German project (Bundesland identified) | +20 |
| Architect firm identified | +15 |
| Bauherr identified | +10 |
| Large scale ≥ 2,000 m² or ≥ 20 units | +10 |

Score > 70 = **Hot lead** (shown expanded by default, highlighted red).
