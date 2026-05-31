"""
Solarlux Lead Intelligence Dashboard
Internal sales tool — multi-source construction project leads.
"""
import base64
import json
import logging
import os
import time
from pathlib import Path

from PIL import Image
import streamlit as st

_ICON_PATH = Path(__file__).parent / "assets" / "solarlux_icon.png"
_favicon = Image.open(_ICON_PATH) if _ICON_PATH.exists() else "🏗️"

st.set_page_config(
    page_title="Solarlux Lead-Generierung",
    page_icon=_favicon,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
  /* ── Globals ── */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
  html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

  :root {
    --red:    #E30613;
    --green:  #16a34a;
    --amber:  #d97706;
    --grey:   #6b7280;
    --bg:     #f9fafb;
    --card:   #ffffff;
    --border: #e5e7eb;
    --text:   #111827;
    --muted:  #6b7280;
  }

  footer { visibility: hidden; }
  #MainMenu { visibility: hidden; }

  /* ── Header ── */
  .sl-header {
    display: flex; align-items: center; gap: 12px;
    padding: 8px 0 20px 0;
  }
  .sl-brand {
    display: flex; flex-direction: column; gap: 2px;
  }
  .sl-logo {
    font-size: 22px; font-weight: 800; color: var(--red);
    letter-spacing: -0.5px; line-height: 1;
  }
  .sl-tagline {
    font-size: 11px; color: var(--muted); font-weight: 400;
    letter-spacing: 0.01em;
  }
  .sl-divider {
    height: 2px; background: var(--red);
    border-radius: 1px; margin-bottom: 24px;
  }

  /* ── Stat cards ── */
  .stat-row {
    display: grid; grid-template-columns: repeat(4, 1fr);
    gap: 12px; margin-bottom: 28px;
  }
  .stat-card {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 12px; padding: 18px 20px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04);
  }
  .stat-label {
    font-size: 11px; font-weight: 600; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 6px;
  }
  .stat-value {
    font-size: 28px; font-weight: 800; color: var(--text); line-height: 1;
  }
  .stat-sub {
    font-size: 11px; color: var(--muted); margin-top: 4px;
  }
  .stat-live  { color: var(--green); }
  .stat-demo  { color: var(--amber); }

  /* ── Section title ── */
  .section-title {
    font-size: 13px; font-weight: 700; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.08em;
    margin: 0 0 14px 0;
  }

  /* ── Lead cards (expander styling) ── */
  div[data-testid="stExpander"] {
    background: var(--card) !important;
    border: 1px solid var(--border) !important;
    border-radius: 12px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    margin-bottom: 8px !important;
    overflow: hidden;
  }
  div[data-testid="stExpander"]:hover {
    border-color: #d1d5db !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  }
  div[data-testid="stExpander"] summary {
    padding: 14px 18px !important;
    font-size: 14px !important;
    font-weight: 600 !important;
    color: var(--text) !important;
  }
  div[data-testid="stExpander"] summary:hover {
    background: var(--bg) !important;
  }
  div[data-testid="stExpander"] > details > div {
    padding: 0 18px 18px 18px !important;
    border-top: 1px solid var(--border);
  }

  /* ── Score dot ── */
  .dot {
    display: inline-flex; align-items: center; justify-content: center;
    width: 36px; height: 36px; border-radius: 50%;
    font-size: 12px; font-weight: 800; flex-shrink: 0;
  }
  .dot-green { background: #dcfce7; color: var(--green); }
  .dot-amber { background: #fef3c7; color: var(--amber); }
  .dot-grey  { background: #f3f4f6; color: var(--grey);  }

  /* ── Chip tags ── */
  .chip {
    display: inline-block; background: var(--bg);
    border: 1px solid var(--border); border-radius: 999px;
    padding: 2px 10px; font-size: 11px; font-weight: 500;
    color: var(--muted); margin-right: 4px;
  }
  .chip-red { background: #fff1f2; border-color: #fecdd3; color: var(--red); }

  /* ── Detail grid ── */
  .detail-grid {
    display: grid; grid-template-columns: 1fr 1fr;
    gap: 8px 24px; margin: 14px 0;
  }
  .detail-row { display: flex; flex-direction: column; gap: 1px; }
  .detail-label { font-size: 10px; font-weight: 600; color: var(--muted);
                  text-transform: uppercase; letter-spacing: 0.06em; }
  .detail-value { font-size: 13px; color: var(--text); font-weight: 500; }

  /* ── Actor pill ── */
  .actor-pill {
    display: inline-flex; align-items: center; gap: 6px;
    background: var(--bg); border: 1px solid var(--border);
    border-radius: 8px; padding: 6px 10px;
    font-size: 12px; margin: 3px 3px 3px 0;
  }
  .actor-role {
    font-size: 10px; font-weight: 600; color: var(--red);
    text-transform: uppercase; letter-spacing: 0.04em;
  }

  /* ── Info banner ── */
  .info-banner {
    background: #fffbeb; border: 1px solid #fde68a;
    border-radius: 10px; padding: 10px 16px;
    font-size: 13px; color: #92400e; margin-bottom: 20px;
  }

  /* ── Empty state ── */
  .empty {
    text-align: center; padding: 60px 0; color: var(--muted);
  }
  .empty-icon { font-size: 36px; margin-bottom: 10px; }
  .empty-text { font-size: 15px; font-weight: 500; }
  .empty-sub  { font-size: 13px; margin-top: 4px; }

  /* ── Lookalike section ── */
  .match-card {
    background: var(--card); border: 1px solid var(--border);
    border-radius: 12px; padding: 16px 20px; margin-bottom: 10px;
    display: flex; align-items: flex-start; gap: 16px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
  }
  .match-score-circle {
    width: 52px; height: 52px; border-radius: 50%;
    display: flex; flex-direction: column; align-items: center;
    justify-content: center; flex-shrink: 0;
    font-size: 18px; font-weight: 800; line-height: 1;
  }
  .match-score-sub { font-size: 9px; font-weight: 500; opacity: 0.7; }
  .match-green { background: #dcfce7; color: var(--green); }
  .match-amber { background: #fef3c7; color: var(--amber); }
  .ref-card {
    background: #fff1f2; border: 1px solid #fecdd3;
    border-radius: 10px; padding: 14px 18px; margin-bottom: 16px;
  }

  /* ── Sidebar ── */
  section[data-testid="stSidebar"] {
    background: var(--card) !important;
    border-right: 1px solid var(--border) !important;
  }
  .sb-label {
    font-size: 10px; font-weight: 700; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.1em;
    margin: 20px 0 8px 0;
  }
  .sb-stat {
    font-size: 13px; color: var(--text); line-height: 1.7;
  }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
SEED_PATH = Path(__file__).parent / "seed_data.json"
ICON_PATH = Path(__file__).parent / "assets" / "solarlux_icon.png"


def _icon_img_tag(height: int = 38) -> str:
    """Return an <img> tag with the PNG icon embedded as a base64 data URL."""
    try:
        b64 = base64.b64encode(ICON_PATH.read_bytes()).decode()
        return (
            f'<img src="data:image/png;base64,{b64}" '
            f'height="{height}" style="flex-shrink:0;margin-top:2px"/>'
        )
    except Exception:
        return ""


def get_api_key() -> str | None:
    try:
        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        return os.environ.get("ANTHROPIC_API_KEY")


def load_seed_data() -> list[dict]:
    if not SEED_PATH.exists():
        return []
    with open(SEED_PATH, encoding="utf-8") as f:
        data = json.load(f)
    for lead in data:
        raw = lead.get("actors")
        if isinstance(raw, str):
            try:
                lead["actors"] = json.loads(raw)
            except Exception:
                lead["actors"] = []
        elif not isinstance(raw, list):
            lead["actors"] = []
    return data


def load_db_leads(min_score: int = 0) -> list[dict]:
    try:
        from db import init_db, get_all_leads
        init_db()
        return get_all_leads(min_score=min_score)
    except Exception as e:
        logging.warning("DB load failed: %s", e)
        return []


def get_stats() -> dict:
    try:
        from db import get_cache_stats
        return get_cache_stats()
    except Exception:
        return {"total_records": 0, "oldest_first_seen": "—",
                "newest_last_seen": "—", "size_kb": 0, "cap": 500}


def score_dot(score: int) -> str:
    if score >= 70:
        css = "dot-green"
    elif score >= 40:
        css = "dot-amber"
    else:
        css = "dot-grey"
    return f'<div class="dot {css}">{score}</div>'


def score_color(score: int) -> str:
    if score >= 70:   return "var(--green)"
    elif score >= 40: return "var(--amber)"
    else:             return "var(--grey)"


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(f"""
    <div style="padding:16px 0 4px 0;display:flex;align-items:center;gap:10px">
      {_icon_img_tag(height=30)}
      <div>
        <div style="font-size:17px;font-weight:800;color:#E30613;letter-spacing:-0.5px">SOLARLUX</div>
        <div style="font-size:11px;color:#9ca3af;margin-top:2px">Lead-Generierung</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # Daten
    st.markdown('<div class="sb-label">Daten</div>', unsafe_allow_html=True)
    run_scrape = st.button("🔄 Live-Suche starten", use_container_width=True,
                           help="BauNetz.de · competitionline · architektensuche (~60–90 Sek.)")

    # Filter
    st.markdown('<div class="sb-label">Filter</div>', unsafe_allow_html=True)
    min_score = st.slider("Mindest-Score", 0, 100, 0, step=5)
    filter_german = st.checkbox("Nur Deutschland")
    sort_by = st.selectbox("Sortieren nach", ["Relevanz ↓", "Zuletzt gesehen ↓", "Erstmals gesehen ↓"])

    # Cache
    st.markdown('<div class="sb-label">Cache</div>', unsafe_allow_html=True)
    stats = get_stats()
    last_upd = (stats["newest_last_seen"] or "—")[:16].replace("T", " ")
    st.markdown(
        f'<div class="sb-stat">'
        f'<b>{stats["total_records"]}</b> / {stats["cap"]} Einträge<br>'
        f'Aktualisiert: {last_upd}<br>'
        f'Größe: {stats["size_kb"]} KB'
        f'</div>',
        unsafe_allow_html=True,
    )
    st.markdown("")
    confirm_clear = st.checkbox("Löschen bestätigen", value=False)
    if st.button("🗑️ Cache leeren", disabled=not confirm_clear, use_container_width=True):
        from db import clear_cache, init_db
        clear_cache(); init_db()
        st.success("Cache wurde geleert.")
        time.sleep(0.8)
        st.rerun()

    # Bewertungsregeln (eingeklappt)
    with st.expander("Bewertungsregeln"):
        st.markdown("""
| Pkt | Kriterium |
|---|---|
| +45 | MFH / Hotel / Büro / Mixed-Use |
| +25 | Umbau / Schule / Kultur |
| +20 | Deutsches Projekt |
| +15 | Architekturbüro bekannt |
| +10 | Bauherr bekannt |
| +10 | Größe ≥ 2.000 m² / 20 WE |
""")

# ---------------------------------------------------------------------------
# Live scraping
# ---------------------------------------------------------------------------
if run_scrape:
    api_key = get_api_key()
    if not api_key:
        st.error("❌ Kein Anthropic API-Key gefunden. Bitte `ANTHROPIC_API_KEY` in den Streamlit-Secrets hinterlegen.")
    else:
        os.environ["ANTHROPIC_API_KEY"] = api_key
        with st.spinner("Suche läuft — ca. 60–90 Sekunden…"):
            try:
                from pipeline import run_pipeline
                summary = run_pipeline(limit_per_source=15)
                st.success(
                    f"✅ {summary['inserted']} neu · {summary['updated']} aktualisiert · "
                    f"{summary['cache_stats']['total_records']} / {summary['cache_stats']['cap']} im Cache"
                )
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Suche fehlgeschlagen: {e}")

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
db_leads  = load_db_leads(min_score=0)
using_seed = not db_leads
all_leads  = db_leads if db_leads else load_seed_data()

leads = [l for l in all_leads if l.get("relevance_score", 0) >= min_score]
if filter_german:
    leads = [l for l in leads if l.get("bundesland")]

if sort_by == "Zuletzt gesehen ↓":
    leads.sort(key=lambda l: l.get("last_seen") or "", reverse=True)
elif sort_by == "Erstmals gesehen ↓":
    leads.sort(key=lambda l: l.get("first_seen") or "", reverse=True)

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(f"""
<div class="sl-header">
  {_icon_img_tag(height=42)}
  <div class="sl-brand">
    <div class="sl-logo">SOLARLUX</div>
    <div class="sl-tagline">Lead-Generierung &nbsp;·&nbsp; Bauprojekt-Radar für Deutschland &amp; Europa</div>
  </div>
</div>
<div class="sl-divider"></div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Stat cards
# ---------------------------------------------------------------------------
total     = len(all_leads)
avg_score = round(sum(l.get("relevance_score", 0) for l in all_leads) / total, 1) if total else 0
hot       = sum(1 for l in all_leads if l.get("relevance_score", 0) >= 70)
src_label = f"{stats['total_records']} / {stats['cap']}" if not using_seed else "Demo"
src_sub   = "Live-Daten" if not using_seed else "Demo-Daten"
src_cls   = "stat-live" if not using_seed else "stat-demo"

st.markdown(f"""
<div class="stat-row">
  <div class="stat-card">
    <div class="stat-label">Leads gesamt</div>
    <div class="stat-value">{total}</div>
    <div class="stat-sub">aus allen Quellen</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Ø Relevanz</div>
    <div class="stat-value">{avg_score}</div>
    <div class="stat-sub">von 100 Punkten</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Top-Leads</div>
    <div class="stat-value">{hot}</div>
    <div class="stat-sub">Score ≥ 70</div>
  </div>
  <div class="stat-card">
    <div class="stat-label">Cache</div>
    <div class="stat-value" style="font-size:22px">{src_label}</div>
    <div class="stat-sub {src_cls}">{src_sub}</div>
  </div>
</div>
""", unsafe_allow_html=True)

if using_seed:
    st.markdown(
        '<div class="info-banner">📦 Demo-Daten werden angezeigt — starte eine Live-Suche, um den Cache zu befüllen.</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Leads list
# ---------------------------------------------------------------------------
st.markdown(f'<div class="section-title">{len(leads)} Leads &nbsp;·&nbsp; Score ≥ {min_score}'
            + (" &nbsp;·&nbsp; Nur Deutschland" if filter_german else "")
            + f" &nbsp;·&nbsp; {sort_by}</div>", unsafe_allow_html=True)

if not leads:
    st.markdown("""
<div class="empty">
  <div class="empty-icon">🏗️</div>
  <div class="empty-text">Keine Leads entsprechen den Filtern.</div>
  <div class="empty-sub">Mindest-Score senken oder Live-Suche starten.</div>
</div>
""", unsafe_allow_html=True)
else:
    for lead in leads:
        score  = lead.get("relevance_score", 0)
        name   = lead.get("project_name") or "Unknown project"
        city   = lead.get("city") or "—"
        bl     = lead.get("bundesland") or ""
        ptype  = lead.get("project_type") or "—"
        arch   = lead.get("architect_firm") or "—"
        actors = lead.get("actors") or []
        t_seen = lead.get("times_seen", 1)

        # Score indicator prefix in label
        if score >= 70:   dot = "●"
        elif score >= 40: dot = "◑"
        else:             dot = "○"

        location = f"{city}" + (f", {bl}" if bl and bl != "—" else "")
        label = f"{dot} {score}   {name}   ·   {location}   ·   {ptype}"

        with st.expander(label, expanded=False):
            # Top row: score + chips
            arch_chip  = f'<span class="chip">{arch}</span>' if arch != "—" else ""
            bauherr    = lead.get("bauherr") or ""
            bauherr_chip = f'<span class="chip">{bauherr}</span>' if bauherr else ""
            seen_chip  = f'<span class="chip">{t_seen}× gesichtet</span>'
            src_chip   = f'<span class="chip chip-red">{lead.get("source") or "—"}</span>'

            st.markdown(
                f'<div style="margin:12px 0 4px 0">{arch_chip}{bauherr_chip}{seen_chip}{src_chip}</div>',
                unsafe_allow_html=True,
            )

            # Detail grid
            completion = lead.get("estimated_completion") or "—"
            scale      = lead.get("scale_units_or_sqm") or "—"
            url        = lead.get("source_url") or ""
            link_html  = f'<a href="{url}" target="_blank" style="color:var(--red);font-size:12px">Quelle öffnen ↗</a>' if url else "—"

            st.markdown(f"""
<div class="detail-grid">
  <div class="detail-row">
    <span class="detail-label">Projekttyp</span>
    <span class="detail-value">{ptype}</span>
  </div>
  <div class="detail-row">
    <span class="detail-label">Standort</span>
    <span class="detail-value">{location}</span>
  </div>
  <div class="detail-row">
    <span class="detail-label">Fertigstellung</span>
    <span class="detail-value">{completion}</span>
  </div>
  <div class="detail-row">
    <span class="detail-label">Größe</span>
    <span class="detail-value">{scale}</span>
  </div>
  <div class="detail-row">
    <span class="detail-label">Relevanz</span>
    <span class="detail-value" style="color:{score_color(score)};font-weight:700">{score} / 100</span>
  </div>
  <div class="detail-row">
    <span class="detail-label">Quelle</span>
    <span class="detail-value">{link_html}</span>
  </div>
</div>
""", unsafe_allow_html=True)

            # Actors
            if actors:
                st.markdown('<div class="detail-label" style="margin-bottom:6px">Personen &amp; Firmen</div>',
                            unsafe_allow_html=True)
                pills = ""
                for a in actors:
                    aname = a.get("name") or "—"
                    arole = a.get("role") or ""
                    afirm = a.get("firm") or ""
                    aemail = a.get("email") or ""
                    extra = ""
                    if afirm: extra += f" · {afirm}"
                    if aemail: extra += f' · <a href="mailto:{aemail}" style="color:var(--red)">{aemail}</a>'
                    pills += f'<div class="actor-pill"><span class="actor-role">{arole}</span><span>{aname}{extra}</span></div>'
                st.markdown(pills, unsafe_allow_html=True)

                # Outreach email
                emails = [a.get("email") for a in actors if a.get("email")]
                if emails:
                    st.markdown("")
                    btn_key = f"email_{lead.get('source_url','')[:40]}"
                    if st.button("✉️ Akquise-E-Mail generieren", key=btn_key):
                        actor_name = next((a.get("name") for a in actors if a.get("email")), "")
                        actor_firm = next((a.get("firm") for a in actors if a.get("email")), "")
                        with st.spinner("Wird generiert…"):
                            try:
                                import anthropic
                                client = anthropic.Anthropic(api_key=get_api_key())
                                prompt = (
                                    f"Schreibe eine kurze, professionelle Akquise-E-Mail auf Deutsch "
                                    f"von Solarlux (Hersteller von Glasfassaden und Schiebetürsystemen) "
                                    f"an {actor_name} von {actor_firm or arch} "
                                    f"bezüglich des Projekts '{name}' in {city}. "
                                    f"Projekttyp: {ptype}. "
                                    f"Max. 120 Wörter, freundlich und konkret."
                                )
                                msg = client.messages.create(
                                    model="claude-haiku-4-5-20251001",
                                    max_tokens=300,
                                    messages=[{"role": "user", "content": prompt}],
                                )
                                st.text_area("Akquise-E-Mail", msg.content[0].text, height=180)
                            except Exception as e:
                                st.error(f"Generierung fehlgeschlagen: {e}")

            # Timestamps
            fs = (lead.get("first_seen") or "")[:16].replace("T", " ")
            ls = (lead.get("last_seen")  or "")[:16].replace("T", " ")
            st.markdown(
                f'<div style="font-size:11px;color:var(--muted);margin-top:12px;padding-top:10px;'
                f'border-top:1px solid var(--border)">Erstmals gesehen: {fs or "—"} UTC &nbsp;·&nbsp; Zuletzt gesehen: {ls or "—"} UTC</div>',
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------------------
# Digital Twins — Lookalike Matching
# ---------------------------------------------------------------------------
st.markdown("<br>", unsafe_allow_html=True)
st.markdown('<div class="section-title">Digitale Zwillinge — Lookalike-Matching</div>', unsafe_allow_html=True)

try:
    from lookalike import REFERENCE_FIRM, find_lookalikes

    st.markdown(f"""
<div class="ref-card">
  <span style="font-size:11px;font-weight:700;color:#9f1239;text-transform:uppercase;letter-spacing:0.06em">Referenzfirma</span><br>
  <span style="font-size:15px;font-weight:700;color:#111">{REFERENCE_FIRM['firm_name']}</span>
  <span style="color:#9ca3af;font-size:13px"> · {REFERENCE_FIRM['city']} · {REFERENCE_FIRM['project_type']} · {REFERENCE_FIRM['typical_scale']}</span>
</div>
""", unsafe_allow_html=True)

    if all_leads:
        matches = find_lookalikes(REFERENCE_FIRM, all_leads, top_n=3)
        if matches:
            for m in matches:
                ms  = m.get("match_score", 0)
                cls = "match-green" if ms >= 50 else "match-amber"
                st.markdown(f"""
<div class="match-card">
  <div class="match-score-circle {cls}">
    {ms}<div class="match-score-sub">/100</div>
  </div>
  <div>
    <div style="font-size:14px;font-weight:700;color:var(--text)">{m.get('project_name','—')}</div>
    <div style="font-size:12px;color:var(--muted);margin-top:2px">
      {m.get('city','—')} · {m.get('bundesland','—')} · {m.get('project_type','—')}
    </div>
    <div style="font-size:12px;color:var(--text);margin-top:6px">✓ {m.get('match_reason','')}</div>
  </div>
</div>
""", unsafe_allow_html=True)
        else:
            st.info("Keine passenden Leads für die Referenzfirma gefunden.")
    else:
        st.info("Keine Leads geladen.")
except Exception as e:
    st.warning(f"Lookalike-Matching nicht verfügbar: {e}")
