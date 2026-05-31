"""
SQLite persistence layer for Solarlux leads.
The database is the persistent cache — it is NEVER auto-wiped.
Each run appends new leads and merges updates into existing ones.
"""
import difflib
import json
import logging
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("leads.db")
MAX_RECORDS = 500  # auto-trim threshold; evict lowest-score / oldest-last_seen first

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS leads (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name         TEXT,
    city                 TEXT,
    bundesland           TEXT,
    project_type         TEXT,
    architect_firm       TEXT,
    bauherr              TEXT,
    estimated_completion TEXT,
    scale_units_or_sqm   TEXT,
    source_url           TEXT UNIQUE,
    source               TEXT,
    actors               TEXT,
    relevance_score      INTEGER DEFAULT 0,
    scraped_at           TEXT,
    first_seen           TEXT,
    last_seen            TEXT,
    times_seen           INTEGER DEFAULT 1
)
"""

# Columns added after initial schema — safe migration via ALTER TABLE
MIGRATION_COLS = [
    ("source",      "TEXT"),
    ("actors",      "TEXT"),
    ("first_seen",  "TEXT"),
    ("last_seen",   "TEXT"),
    ("times_seen",  "INTEGER DEFAULT 1"),
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize(s: str) -> str:
    """Lowercase, strip accents, remove punctuation for fuzzy comparison."""
    s = (s or "").lower().strip()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9\s]", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _fuzzy_key(lead: dict) -> str:
    return _normalize((lead.get("project_name") or "") + " " + (lead.get("city") or ""))


def _actors_json(lead: dict) -> str:
    actors = lead.get("actors")
    return json.dumps(actors, ensure_ascii=False) if actors else "[]"


def _merge_sources(existing_source: str | None, new_source: str | None) -> str:
    """Merge source strings, deduplicating."""
    parts = [s.strip() for s in (existing_source or "").split(",") if s.strip()]
    for ns in (new_source or "").split(","):
        ns = ns.strip()
        if ns and ns not in parts:
            parts.append(ns)
    return ", ".join(parts)


def _merge_actors(existing_json: str | None, new_actors: list) -> str:
    """Merge actor lists, deduplicating by name."""
    try:
        existing = json.loads(existing_json or "[]")
    except Exception:
        existing = []
    existing_names = {(a.get("name") or "").lower() for a in existing}
    for a in (new_actors or []):
        if (a.get("name") or "").lower() not in existing_names:
            existing.append(a)
            existing_names.add((a.get("name") or "").lower())
    return json.dumps(existing, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def init_db() -> None:
    """Create the leads table; safely migrate any missing columns."""
    with _connect() as conn:
        conn.execute(CREATE_TABLE_SQL)
        existing_cols = {row[1] for row in conn.execute("PRAGMA table_info(leads)")}
        for col, typedef in MIGRATION_COLS:
            if col not in existing_cols:
                conn.execute(f"ALTER TABLE leads ADD COLUMN {col} {typedef}")
        conn.commit()


def upsert_lead(lead: dict) -> str:
    """
    Insert or merge a lead into the persistent cache.
    Matching priority:
      1. source_url exact match
      2. fuzzy match on normalized (project_name + city), ratio > 0.85
    Returns: 'inserted' | 'updated' | 'skipped' (on error)
    """
    now = _now()
    new_key = _fuzzy_key(lead)

    with _connect() as conn:
        # --- Try exact source_url match ---
        row = None
        if lead.get("source_url"):
            row = conn.execute(
                "SELECT * FROM leads WHERE source_url = ?", (lead["source_url"],)
            ).fetchone()

        # --- Fuzzy name+city match if no exact URL hit ---
        if row is None and new_key.strip():
            candidates = conn.execute(
                "SELECT * FROM leads WHERE project_name IS NOT NULL"
            ).fetchall()
            for c in candidates:
                c_key = _normalize((c["project_name"] or "") + " " + (c["city"] or ""))
                if c_key and difflib.SequenceMatcher(None, new_key, c_key).ratio() > 0.85:
                    row = c
                    break

        if row is not None:
            # --- UPDATE existing ---
            existing = dict(row)
            merged_source  = _merge_sources(existing.get("source"), lead.get("source"))
            merged_actors  = _merge_actors(existing.get("actors"), lead.get("actors") or [])
            higher_score   = max(existing.get("relevance_score") or 0, lead.get("relevance_score") or 0)

            # Fill in any previously-null fields with newly found values
            def pick(field):
                return existing.get(field) or lead.get(field)

            conn.execute("""
                UPDATE leads SET
                    city             = ?,
                    bundesland       = ?,
                    project_type     = ?,
                    architect_firm   = ?,
                    bauherr          = ?,
                    estimated_completion = ?,
                    scale_units_or_sqm   = ?,
                    source           = ?,
                    actors           = ?,
                    relevance_score  = ?,
                    last_seen        = ?,
                    times_seen       = times_seen + 1
                WHERE id = ?
            """, (
                pick("city"), pick("bundesland"), pick("project_type"),
                pick("architect_firm"), pick("bauherr"),
                pick("estimated_completion"), pick("scale_units_or_sqm"),
                merged_source, merged_actors, higher_score,
                now, existing["id"],
            ))
            conn.commit()
            return "updated"

        else:
            # --- INSERT new ---
            conn.execute("""
                INSERT OR IGNORE INTO leads (
                    project_name, city, bundesland, project_type,
                    architect_firm, bauherr, estimated_completion,
                    scale_units_or_sqm, source_url, source, actors,
                    relevance_score, scraped_at, first_seen, last_seen, times_seen
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            """, (
                lead.get("project_name"), lead.get("city"), lead.get("bundesland"),
                lead.get("project_type"), lead.get("architect_firm"), lead.get("bauherr"),
                lead.get("estimated_completion"), lead.get("scale_units_or_sqm"),
                lead.get("source_url"), lead.get("source"), _actors_json(lead),
                lead.get("relevance_score") or 0,
                lead.get("scraped_at") or now, now, now,
            ))
            conn.commit()
            return "inserted"


def auto_trim() -> int:
    """
    Evict excess rows if total > MAX_RECORDS.
    Eviction order: lowest relevance_score first, then oldest last_seen.
    Returns number of rows evicted.
    """
    with _connect() as conn:
        total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        excess = total - MAX_RECORDS
        if excess <= 0:
            return 0
        conn.execute("""
            DELETE FROM leads WHERE id IN (
                SELECT id FROM leads
                ORDER BY relevance_score ASC, last_seen ASC
                LIMIT ?
            )
        """, (excess,))
        conn.commit()
        logger.info("Auto-trim: evicted %d low-value leads (cap=%d)", excess, MAX_RECORDS)
        return excess


def get_all_leads(min_score: int = 0) -> list[dict]:
    """Return all leads with relevance_score >= min_score, sorted descending."""
    with _connect() as conn:
        rows = conn.execute("""
            SELECT * FROM leads
            WHERE relevance_score >= ?
            ORDER BY relevance_score DESC, last_seen DESC
        """, (min_score,)).fetchall()

    result = []
    for row in rows:
        d = dict(row)
        try:
            d["actors"] = json.loads(d.get("actors") or "[]")
        except Exception:
            d["actors"] = []
        result.append(d)
    return result


def get_cache_stats() -> dict:
    """Return cache metadata for display in the UI."""
    with _connect() as conn:
        row = conn.execute("""
            SELECT
                COUNT(*) as total,
                MIN(first_seen) as oldest,
                MAX(last_seen) as newest
            FROM leads
        """).fetchone()

    size_bytes = DB_PATH.stat().st_size if DB_PATH.exists() else 0
    return {
        "total_records": row["total"] if row else 0,
        "oldest_first_seen": (row["oldest"] or "")[:19].replace("T", " ") if row else "—",
        "newest_last_seen":  (row["newest"] or "")[:19].replace("T", " ") if row else "—",
        "size_kb": round(size_bytes / 1024, 1),
        "cap": MAX_RECORDS,
    }


def clear_cache() -> None:
    """Empty the leads table. Manual operation only — never called automatically."""
    with _connect() as conn:
        conn.execute("DELETE FROM leads")
        conn.commit()
    logger.info("Cache cleared manually.")


# Legacy compat — kept so dev scripts don't break; never called from pipeline
def insert_lead(lead: dict) -> bool:
    return upsert_lead(lead) == "inserted"


def clear_db() -> None:
    """Alias for clear_cache() — for dev scripts only."""
    clear_cache()
    init_db()
