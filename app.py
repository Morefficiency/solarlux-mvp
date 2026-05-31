"""
Solarlux Lead Intelligence Dashboard
Internal sales tool — multi-source construction project leads.
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

# ---------------------------------------------------------------------------
# Global CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
  :root {
    --sl-red:   #E30613;
    --green:    #1a7a4a;
    --amber:    #b85c00;
    --grey:     #666;
    --bg-green: #e8f5ee;
    --bg-amber: #fff4e5;
    --bg-grey:  #f2f2f2;
  }

  /* Header */
  .sl-header {
    display: flex; align-items: center; gap: 14px;
    padding: 10px 0 18px 0;
    border-bottom: 3px solid var(--sl-red);
    margin-bottom: 22px;
  }
  .sl-logo    { font-size: 26px; font-weight: 900; color: var(--sl-red); letter-spacing: -1px; }
  .sl-tagline { font-size: 12px; color: #777; margin-top: 2px; }

  /* Metric cards */
  div[data-testid="metric-container"] {
    background: #fafafa; border-radius: 8px;
    padding: 12px 16px; border-left: 4px solid var(--sl-red);
  }

  /* Relevance badges */
  .badge {
    display: inline-block; border-radius: 5px;
    padding: 2px 10px; font-size: 13px; font-weight: 700;
    line-height: 1.6;
  }
  .badge-green { background: var(--bg-green); color: var(--green); }
  .badge-amber { background: var(--bg-amber); color: var(--amber); }
  .badge-grey  { background: var(--bg-grey);  color: var(--grey);  }

  /* Reference firm card */
  .ref-card {
    background: #fff8f8; border: 1px solid #f5c0c0;
    border-radius: 8px; padding: 14px; margin-bottom: 14px;
  }

  /* Lookalike match card */
  .match-card {
    background: #fafafa; border-radius: 8px;
    padding: 12px 16px; border-left: 3px solid #ccc;
    margin-bottom: 8px;
  }

  /* Sidebar section labels */
  .sidebar-section {
    font-size: 11px; font-weight: 700; color: #999;
    text-transform: uppercase; letter-spacing: 0.08em;
    margin: 14px 0 6px 0;
  }

  /* Empty state */
  .empty-state {
    text-align: center; padding: 48px 0; color: #aaa; font-size: 15px;
  }

  footer { visibility: hidden; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
st.markdown("""
<div class="sl-header">
  <svg width="44" height="36" viewBox="0 0 44 36" fill="none" xmlns="http://www.w3.org/2000/svg" style="flex-shrink:0;margin-top:3px">
    <!-- left panel: outer top-left protrudes, leans away from center -->
    <polygon points="0,5 19,2 19,34 0,31" fill="#8c8c8c"/>
    <!-- right panel: mirror -->
    <polygon points="25,2 44,5 44,31 25,34" fill="#8c8c8c"/>
  </svg>
  <div>
    <div class="sl-logo">SOLARLUX</div>
    <div class="sl-tagline">Lead Intelligence · Construction project radar for DACH &amp; Europe</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
SEED_PATH = Path(__file__).parent / "seed_data.json"


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


def relevance_badge(score: int) -> str:
    if score >= 70:
        css, label = "badge-green", f"● {score}"
    elif score >= 40:
        css, label = "badge-amber", f"◑ {score}"
    else:
        css, label = "badge-grey",  f"○ {score}"
    return f'<span class="badge {css}">{label}</span>'


# ---------------------------------------------------------------------------
# Sidebar — 3 grouped sections
# ---------------------------------------------------------------------------
with st.sidebar:
    # ── 1. Data Source ────────────────────────────────────────────────────
    st.markdown('<div class="sidebar-section">Data Source</div>', unsafe_allow_html=True)
    run_scrape = st.button("🔄 Run live scrape", use_container_width=True,
                           help="Fetches from BauNetz.de · competitionline · architektensuche (~60–90 s)")

    # ── 2. Filters ───────────────────────────────────────────────────────
    st.markdown('<div class="sidebar-section">Filters</div>', unsafe_allow_html=True)
    min_score = st.slider("Min. relevance score", 0, 100, 0, step=5)
    filter_german = st.checkbox("German projects only (Bundesland set)")
    sort_by = st.selectbox("Sort by", ["Relevance ↓", "Last seen ↓", "First seen ↓"])

    # ── 3. Cache ─────────────────────────────────────────────────────────
    st.markdown('<div class="sidebar-section">Cache</div>', unsafe_allow_html=True)
    stats = get_stats()
    st.markdown(
        f"**{stats['total_records']} / {stats['cap']}** records  \n"
        f"Last updated: `{stats['newest_last_seen'] or '—'}`  \n"
        f"DB size: `{stats['size_kb']} KB`"
    )

    st.divider()
    confirm_clear = st.checkbox("⚠️ Confirm cache clear", value=False,
                                help="Check this box to enable the clear button")
    clear_btn = st.button("🗑️ Clear cache", disabled=not confirm_clear,
                          use_container_width=True, type="secondary")
    if clear_btn and confirm_clear:
        from db import clear_cache, init_db
        clear_cache()
        init_db()
        st.success("Cache cleared.")
        time.sleep(0.8)
        st.rerun()

    # ── Scoring legend ────────────────────────────────────────────────────
    st.divider()
    st.markdown("""
**Scoring rules**
| Points | Criterion |
|---|---|
| +45 | MFH / Hotel / Büro / Mixed-use |
| +25 | Umbau / Schule / Culture |
| +20 | German project (Bundesland set) |
| +15 | Architect firm identified |
| +10 | Bauherr identified |
| +10 | Scale ≥ 2,000 m² or ≥ 20 units |
""")

# ---------------------------------------------------------------------------
# Live scraping
# ---------------------------------------------------------------------------
if run_scrape:
    api_key = get_api_key()
    if not api_key:
        st.error("❌ No Anthropic API key found. Add `ANTHROPIC_API_KEY` to Streamlit Secrets.")
    else:
        os.environ["ANTHROPIC_API_KEY"] = api_key
        with st.spinner("Scraping in progress — this takes ~60–90 seconds…"):
            try:
                from pipeline import run_pipeline
                summary = run_pipeline(limit_per_source=15)
                st.success(
                    f"✅ Done — **{summary['inserted']}** new leads added, "
                    f"**{summary['updated']}** updated. "
                    f"Cache: {summary['cache_stats']['total_records']} / {summary['cache_stats']['cap']} records."
                )
                time.sleep(1)
                st.rerun()
            except Exception as e:
                st.error(f"Scrape failed: {e}")

# ---------------------------------------------------------------------------
# Load data — DB first, seed fallback when empty
# ---------------------------------------------------------------------------
db_leads = load_db_leads(min_score=0)
using_seed = not db_leads
all_leads  = db_leads if db_leads else load_seed_data()

# Apply filters
leads = [l for l in all_leads if l.get("relevance_score", 0) >= min_score]
if filter_german:
    leads = [l for l in leads if l.get("bundesland")]

# Apply sort
if sort_by == "Last seen ↓":
    leads.sort(key=lambda l: l.get("last_seen") or "", reverse=True)
elif sort_by == "First seen ↓":
    leads.sort(key=lambda l: l.get("first_seen") or "", reverse=True)
# default: already sorted by relevance_score DESC from DB / seed

# ---------------------------------------------------------------------------
# Metrics row
# ---------------------------------------------------------------------------
total      = len(all_leads)
avg_score  = round(sum(l.get("relevance_score", 0) for l in all_leads) / total, 1) if total else 0
hot_count  = sum(1 for l in all_leads if l.get("relevance_score", 0) >= 70)
cache_disp = (f"{stats['total_records']} / {stats['cap']}" if not using_seed
              else "seed data")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total leads",     total)
c2.metric("Avg. relevance",  avg_score)
c3.metric("High-value (≥70)", hot_count)
c4.metric("Cache", cache_disp,
          delta="live" if not using_seed else "demo fallback",
          delta_color="normal" if not using_seed else "off")

if using_seed:
    st.info("📦 Showing demo data (seed_data.json). Run a live scrape to populate the cache.")

st.divider()

# ---------------------------------------------------------------------------
# Leads table
# ---------------------------------------------------------------------------
if not leads:
    st.markdown("""
<div class="empty-state">
  🏗️ No leads match your filters.<br>
  <small>Lower the min. relevance slider or run a live scrape.</small>
</div>
""", unsafe_allow_html=True)
else:
    st.markdown(f"**{len(leads)} leads** · score ≥ {min_score}"
                + (" · German only" if filter_german else "")
                + f" · {sort_by}")
    st.markdown("")

    for lead in leads:
        score    = lead.get("relevance_score", 0)
        name     = lead.get("project_name") or "Unknown project"
        city     = lead.get("city") or "—"
        bl       = lead.get("bundesland") or "—"
        ptype    = lead.get("project_type") or "—"
        arch     = lead.get("architect_firm") or "—"
        source   = lead.get("source") or "—"
        actors   = lead.get("actors") or []
        t_seen   = lead.get("times_seen", 1)

        badge_html = relevance_badge(score)
        expander_label = f"{name}  ·  {city}  ·  {ptype}"

        with st.expander(expander_label, expanded=(score >= 70)):
            # Badge + times_seen in header area
            st.markdown(
                f"{badge_html} &nbsp; "
                f"<span style='font-size:12px;color:#888'>seen {t_seen}×</span>",
                unsafe_allow_html=True,
            )
            st.markdown("")

            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Project:** {name}")
                st.markdown(f"**City:** {city} &nbsp; **Bundesland:** {bl}")
                st.markdown(f"**Type:** {ptype}")
                st.markdown(f"**Relevance score:** {score} / 100")
                st.markdown(f"**Source:** {source}")
            with col2:
                st.markdown(f"**Architect:** {arch}")
                st.markdown(f"**Bauherr:** {lead.get('bauherr') or '—'}")
                st.markdown(f"**Completion:** {lead.get('estimated_completion') or '—'}")
                st.markdown(f"**Scale:** {lead.get('scale_units_or_sqm') or '—'}")
                url = lead.get("source_url")
                if url:
                    st.markdown(f"**Link:** [{url[:55]}…]({url})")

            # Actor table
            if actors:
                st.markdown("**Actors:**")
                actor_rows = []
                for a in actors:
                    actor_rows.append({
                        "Name":  a.get("name") or "—",
                        "Role":  a.get("role") or "—",
                        "Firm":  a.get("firm") or "—",
                        "Email": a.get("email") or "—",
                        "Phone": a.get("phone") or "—",
                    })
                st.dataframe(actor_rows, use_container_width=True, hide_index=True)

                # Outreach email button — only if any actor has email
                emails = [a.get("email") for a in actors if a.get("email")]
                if emails:
                    btn_key = f"email_{lead.get('source_url','')[:40]}"
                    if st.button("✉️ Generate outreach email", key=btn_key):
                        actor_name  = next((a.get("name") for a in actors if a.get("email")), "")
                        actor_firm  = next((a.get("firm") for a in actors if a.get("email")), "")
                        with st.spinner("Generating…"):
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
                                st.text_area("Outreach email (DE)", msg.content[0].text, height=200)
                            except Exception as e:
                                st.error(f"Generation failed: {e}")

            fs = (lead.get("first_seen") or "")[:19].replace("T", " ")
            ls = (lead.get("last_seen")  or "")[:19].replace("T", " ")
            st.caption(f"First seen: {fs or '—'} UTC · Last seen: {ls or '—'} UTC")

# ---------------------------------------------------------------------------
# Digitale Zwillinge — Lookalike Matching
# ---------------------------------------------------------------------------
st.divider()
st.markdown("## 🔍 Digital Twins — Lookalike Matching")
st.markdown("Leads that best match a reference firm's profile.")

try:
    from lookalike import REFERENCE_FIRM, find_lookalikes

    st.markdown(f"""
<div class="ref-card">
<strong>Reference firm</strong><br>
<b>{REFERENCE_FIRM['firm_name']}</b> &nbsp;·&nbsp;
{REFERENCE_FIRM['city']} &nbsp;·&nbsp;
Focus: <em>{REFERENCE_FIRM['project_type']}</em> &nbsp;·&nbsp;
Typical scale: <em>{REFERENCE_FIRM['typical_scale']}</em>
</div>
""", unsafe_allow_html=True)

    if all_leads:
        matches = find_lookalikes(REFERENCE_FIRM, all_leads, top_n=3)
        if matches:
            for m in matches:
                ms     = m.get("match_score", 0)
                color  = "#1a7a4a" if ms >= 50 else "#b85c00"
                st.markdown(f"""
<div class="match-card">
<span style="color:{color};font-weight:700;font-size:20px">{ms}</span>
<span style="font-size:12px;color:#999">/100</span>
&nbsp;&nbsp;
<strong>{m.get('project_name','—')}</strong>
&nbsp;·&nbsp; {m.get('city','—')} ({m.get('bundesland','—')})
&nbsp;·&nbsp; <em>{m.get('project_type','—')}</em><br>
<span style="font-size:12px;color:#555">✓ {m.get('match_reason','')}</span>
<span style="font-size:11px;color:#bbb;margin-left:12px">Source: {m.get('source','—')}</span>
</div>
""", unsafe_allow_html=True)
        else:
            st.info("No matches found for the reference firm.")
    else:
        st.info("No leads loaded.")
except Exception as e:
    st.warning(f"Lookalike matching unavailable: {e}")
