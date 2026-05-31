"""
Solarlux Lead-Intelligence Dashboard
Streamlit frontend — displays, filters, and live-scrapes construction project leads.
"""
import json
import logging
import os
import time
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Page config — must be first Streamlit call
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Solarlux Lead Intelligence",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Brand styling
# ---------------------------------------------------------------------------
st.markdown("""
<style>
  /* Solarlux red accent */
  :root { --sl-red: #E30613; }

  /* Header bar */
  .sl-header {
    display: flex; align-items: center; gap: 16px;
    padding: 12px 0 20px 0; border-bottom: 3px solid #E30613; margin-bottom: 24px;
  }
  .sl-logo { font-size: 28px; font-weight: 900; color: #E30613; letter-spacing: -1px; }
  .sl-sub  { font-size: 13px; color: #666; margin-top: 2px; }

  /* Metric cards */
  div[data-testid="metric-container"] {
    background: #f8f8f8; border-radius: 8px; padding: 12px 16px;
    border-left: 4px solid #E30613;
  }

  /* Score badge in table */
  .score-high { color: #E30613; font-weight: 700; }
  .score-mid  { color: #e67e00; font-weight: 600; }
  .score-low  { color: #888; }

  /* Expander header tweak */
  .streamlit-expanderHeader { font-weight: 600; }

  /* Hide Streamlit branding footer */
  footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("""
<div class="sl-header">
  <div>
    <div class="sl-logo">SOLARLUX</div>
    <div class="sl-sub">Lead Intelligence — Bauprojekte Deutschland &amp; DACH</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------
SEED_PATH = Path(__file__).parent / "seed_data.json"


def load_seed_data() -> list[dict]:
    if SEED_PATH.exists():
        with open(SEED_PATH, encoding="utf-8") as f:
            return json.load(f)
    return []


def load_from_db(min_score: int = 0) -> list[dict]:
    try:
        from db import init_db, get_all_leads
        init_db()
        return get_all_leads(min_score=min_score)
    except Exception as e:
        logging.warning("DB load failed: %s", e)
        return []


def get_api_key() -> str | None:
    """Try st.secrets first, then environment variable."""
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        return os.environ.get("ANTHROPIC_API_KEY")


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("### ⚙️ Steuerung")

    min_score = st.slider(
        "Mindest-Score", min_value=0, max_value=100, value=0, step=5,
        help="Nur Leads mit Relevanz-Score ≥ diesem Wert anzeigen"
    )

    st.divider()

    run_scrape = st.button(
        "🔄 Live-Scraping starten",
        use_container_width=True,
        help="Aktuelle Projekte von BauNetz.de laden und bewerten"
    )

    st.divider()
    st.markdown("""
**Scoring-Logik**
| Kriterium | Punkte |
|---|---|
| Projekttyp High (MFH, Hotel, Büro…) | +45 |
| Projekttyp Medium (Umbau…) | +25 |
| Deutsches Projekt (Bundesland bekannt) | +20 |
| Architekturbüro identifiziert | +15 |
| Bauherr identifiziert | +10 |
| Großes Volumen (≥2.000 m²) | +10 |
""")

# ---------------------------------------------------------------------------
# Live scraping (triggered by button)
# ---------------------------------------------------------------------------
if run_scrape:
    api_key = get_api_key()
    if not api_key:
        st.error("❌ Kein Anthropic API Key gefunden. Bitte in den Streamlit Secrets unter `ANTHROPIC_API_KEY` hinterlegen.")
    else:
        os.environ["ANTHROPIC_API_KEY"] = api_key
        st.info("🔄 Scraping läuft... (ca. 60–90 Sekunden)")
        progress = st.progress(0, text="Initialisiere...")
        try:
            from pipeline import run_pipeline
            from db import init_db
            init_db()
            leads = run_pipeline(limit=15)
            progress.progress(100, text="Fertig!")
            st.success(f"✅ {len(leads)} Projekte verarbeitet und gespeichert.")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Scraping fehlgeschlagen: {e}")
            progress.empty()

# ---------------------------------------------------------------------------
# Load data — DB first, seed fallback
# ---------------------------------------------------------------------------
db_leads = load_from_db(min_score=0)

if db_leads:
    source_label = "Datenbank (live)"
    all_leads = db_leads
else:
    source_label = "Demo-Daten (seed_data.json)"
    all_leads = load_seed_data()

# Apply score filter
leads = [l for l in all_leads if l.get("relevance_score", 0) >= min_score]

# ---------------------------------------------------------------------------
# Metrics row
# ---------------------------------------------------------------------------
total = len(all_leads)
avg_score = round(sum(l.get("relevance_score", 0) for l in all_leads) / total, 1) if total else 0
hot_count = sum(1 for l in all_leads if l.get("relevance_score", 0) > 70)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Leads gesamt", total)
col2.metric("Ø Relevanz-Score", avg_score)
col3.metric("Hot Leads (> 70)", hot_count)
col4.metric("Datenquelle", source_label)

st.divider()

# ---------------------------------------------------------------------------
# Lead table + expanders
# ---------------------------------------------------------------------------
if not leads:
    st.warning("Keine Leads gefunden. Bitte Score-Filter verringern oder Live-Scraping starten.")
else:
    st.markdown(f"**{len(leads)} Leads** (Score ≥ {min_score}) — sortiert nach Relevanz")
    st.markdown("")

    for lead in leads:
        score = lead.get("relevance_score", 0)
        name  = lead.get("project_name") or "Unbekanntes Projekt"
        city  = lead.get("city") or "—"
        bl    = lead.get("bundesland") or "—"
        ptype = lead.get("project_type") or "—"
        arch  = lead.get("architect_firm") or "—"

        # Score color class
        if score > 70:
            badge = f"🔴 **{score}**"
        elif score > 50:
            badge = f"🟠 **{score}**"
        else:
            badge = f"⚪ {score}"

        label = f"{badge} &nbsp; {name} &nbsp;·&nbsp; {city} ({bl}) &nbsp;·&nbsp; *{ptype}*"

        with st.expander(label, expanded=(score > 70)):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Projektname:** {name}")
                st.markdown(f"**Stadt:** {city}")
                st.markdown(f"**Bundesland:** {bl}")
                st.markdown(f"**Projekttyp:** {ptype}")
                st.markdown(f"**Relevanz-Score:** {score}/100")
            with c2:
                st.markdown(f"**Architekturbüro:** {arch}")
                st.markdown(f"**Bauherr:** {lead.get('bauherr') or '—'}")
                st.markdown(f"**Fertigstellung:** {lead.get('estimated_completion') or '—'}")
                st.markdown(f"**Volumen:** {lead.get('scale_units_or_sqm') or '—'}")
                url = lead.get("source_url")
                if url:
                    st.markdown(f"**Quelle:** [{url[:60]}...]({url})")
            st.caption(f"Gespeichert: {lead.get('scraped_at','—')[:19].replace('T',' ')} UTC")
