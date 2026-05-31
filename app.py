"""
Solarlux Lead-Intelligence Dashboard — v2
Multi-source · Actor identification · Digitale Zwillinge
"""
import json
import logging
import os
import time
from pathlib import Path

import streamlit as st

st.set_page_config(
    page_title="Solarlux Lead Intelligence",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
  :root { --sl-red: #E30613; }
  .sl-header {
    display: flex; align-items: center; gap: 16px;
    padding: 12px 0 20px 0; border-bottom: 3px solid #E30613; margin-bottom: 24px;
  }
  .sl-logo { font-size: 28px; font-weight: 900; color: #E30613; letter-spacing: -1px; }
  .sl-sub  { font-size: 13px; color: #666; margin-top: 2px; }
  div[data-testid="metric-container"] {
    background: #f8f8f8; border-radius: 8px; padding: 12px 16px;
    border-left: 4px solid #E30613;
  }
  .ref-card {
    background: #fff8f8; border: 1px solid #E30613; border-radius: 8px;
    padding: 16px; margin-bottom: 16px;
  }
  .match-card {
    background: #f8f8f8; border-radius: 8px; padding: 12px 16px;
    border-left: 3px solid #888; margin-bottom: 8px;
  }
  .source-badge {
    display: inline-block; background: #eee; border-radius: 4px;
    padding: 2px 8px; font-size: 11px; color: #555; margin-left: 6px;
  }
  footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="sl-header">
  <div>
    <div class="sl-logo">SOLARLUX</div>
    <div class="sl-sub">Lead Intelligence — Bauprojekte Deutschland &amp; DACH</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
SEED_PATH = Path(__file__).parent / "seed_data.json"


def load_seed_data() -> list[dict]:
    if SEED_PATH.exists():
        with open(SEED_PATH, encoding="utf-8") as f:
            data = json.load(f)
        for lead in data:
            if isinstance(lead.get("actors"), str):
                try:
                    lead["actors"] = json.loads(lead["actors"])
                except Exception:
                    lead["actors"] = []
            elif not isinstance(lead.get("actors"), list):
                lead["actors"] = []
        return data
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
        help="Aktuelle Projekte aus allen Quellen laden und bewerten (~60–90s)"
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

**Quellen**
- BauNetz.de (Projekte)
- competitionline.com
- architektensuche.de
""")

# ---------------------------------------------------------------------------
# Live scraping
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
            leads = run_pipeline(limit_per_source=15)
            progress.progress(100, text="Fertig!")
            st.success(f"✅ {len(leads)} Projekte verarbeitet und gespeichert.")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"Scraping fehlgeschlagen: {e}")
            progress.empty()

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
db_leads = load_from_db(min_score=0)
all_leads = db_leads if db_leads else load_seed_data()
leads = [l for l in all_leads if l.get("relevance_score", 0) >= min_score]

# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------
total     = len(all_leads)
avg_score = round(sum(l.get("relevance_score", 0) for l in all_leads) / total, 1) if total else 0
hot_count = sum(1 for l in all_leads if l.get("relevance_score", 0) > 70)

col1, col2, col3 = st.columns(3)
col1.metric("Leads gesamt", total)
col2.metric("Ø Relevanz-Score", avg_score)
col3.metric("Hot Leads (> 70)", hot_count)

st.divider()

# ---------------------------------------------------------------------------
# Lead table
# ---------------------------------------------------------------------------
if not leads:
    st.warning("Keine Leads gefunden. Score-Filter verringern oder Live-Scraping starten.")
else:
    st.markdown(f"**{len(leads)} Leads** (Score ≥ {min_score}) — sortiert nach Relevanz")
    st.markdown("")

    for lead in leads:
        score  = lead.get("relevance_score", 0)
        name   = lead.get("project_name") or "Unbekanntes Projekt"
        city   = lead.get("city") or "—"
        bl     = lead.get("bundesland") or "—"
        ptype  = lead.get("project_type") or "—"
        arch   = lead.get("architect_firm") or "—"
        source = lead.get("source") or "—"
        actors = lead.get("actors") or []

        badge = "🔴 **{}**".format(score) if score > 70 else ("🟠 **{}**".format(score) if score > 50 else "⚪ {}".format(score))
        label = f"{badge} &nbsp; {name} &nbsp;·&nbsp; {city} ({bl}) &nbsp;·&nbsp; *{ptype}*"

        with st.expander(label, expanded=(score > 70)):
            c1, c2 = st.columns(2)
            with c1:
                st.markdown(f"**Projektname:** {name}")
                st.markdown(f"**Stadt:** {city}")
                st.markdown(f"**Bundesland:** {bl}")
                st.markdown(f"**Projekttyp:** {ptype}")
                st.markdown(f"**Relevanz-Score:** {score}/100")
                st.markdown(f"**Quelle:** {source}")
            with c2:
                st.markdown(f"**Architekturbüro:** {arch}")
                st.markdown(f"**Bauherr:** {lead.get('bauherr') or '—'}")
                st.markdown(f"**Fertigstellung:** {lead.get('estimated_completion') or '—'}")
                st.markdown(f"**Volumen:** {lead.get('scale_units_or_sqm') or '—'}")
                url = lead.get("source_url")
                if url:
                    st.markdown(f"**Link:** [{url[:55]}...]({url})")

            # Actors table
            if actors:
                st.markdown("**Akteure:**")
                actor_rows = [
                    {"Name": a.get("name", "—"), "Rolle": a.get("role", "—"), "Firma": a.get("firm") or "—"}
                    for a in actors
                ]
                st.dataframe(actor_rows, use_container_width=True, hide_index=True)

            st.caption(f"Gespeichert: {(lead.get('scraped_at') or '')[:19].replace('T',' ')} UTC")

# ---------------------------------------------------------------------------
# Digitale Zwillinge
# ---------------------------------------------------------------------------
st.divider()
st.markdown("## 🔍 Digitale Zwillinge")
st.markdown("Leads, die dem Profil einer Referenzfirma am stärksten ähneln.")

try:
    from lookalike import REFERENCE_FIRM, find_lookalikes

    # Reference card
    st.markdown(f"""
<div class="ref-card">
<strong>Referenzfirma</strong><br>
<b>{REFERENCE_FIRM['firm_name']}</b> &nbsp;·&nbsp; {REFERENCE_FIRM['city']} &nbsp;·&nbsp;
Fokus: <em>{REFERENCE_FIRM['project_type']}</em> &nbsp;·&nbsp;
Typische Größe: <em>{REFERENCE_FIRM['typical_scale']}</em>
</div>
""", unsafe_allow_html=True)

    if all_leads:
        matches = find_lookalikes(REFERENCE_FIRM, all_leads, top_n=3)
        if matches:
            for i, m in enumerate(matches, 1):
                ms = m.get("match_score", 0)
                badge_color = "#E30613" if ms >= 50 else "#e67e00"
                st.markdown(f"""
<div class="match-card">
<span style="color:{badge_color};font-weight:700;font-size:18px">{ms}</span>
<span style="font-size:13px;color:#888">/100</span>
&nbsp;&nbsp;
<strong>{m.get('project_name','—')}</strong>
&nbsp;·&nbsp; {m.get('city','—')} ({m.get('bundesland','—')})
&nbsp;·&nbsp; <em>{m.get('project_type','—')}</em><br>
<span style="font-size:12px;color:#555">✓ {m.get('match_reason','')}</span>
&nbsp;&nbsp;
<span style="font-size:11px;color:#999">Quelle: {m.get('source','—')}</span>
</div>
""", unsafe_allow_html=True)
        else:
            st.info("Keine passenden Leads für die Referenzfirma gefunden.")
    else:
        st.info("Keine Leads geladen.")
except Exception as e:
    st.warning(f"Lookalike-Matching nicht verfügbar: {e}")
