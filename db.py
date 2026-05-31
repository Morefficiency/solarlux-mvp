"""
SQLite persistence layer for Solarlux leads.
"""
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path("leads.db")

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS leads (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    project_name     TEXT,
    city             TEXT,
    bundesland       TEXT,
    project_type     TEXT,
    architect_firm   TEXT,
    bauherr          TEXT,
    estimated_completion TEXT,
    scale_units_or_sqm   TEXT,
    source_url       TEXT UNIQUE,
    relevance_score  INTEGER DEFAULT 0,
    scraped_at       TEXT
)
"""


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the leads table if it doesn't exist."""
    with _connect() as conn:
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()


def insert_lead(lead: dict) -> bool:
    """
    Insert a lead. Returns True if inserted, False if already exists (by source_url).
    """
    sql = """
    INSERT OR IGNORE INTO leads (
        project_name, city, bundesland, project_type,
        architect_firm, bauherr, estimated_completion,
        scale_units_or_sqm, source_url, relevance_score, scraped_at
    ) VALUES (
        :project_name, :city, :bundesland, :project_type,
        :architect_firm, :bauherr, :estimated_completion,
        :scale_units_or_sqm, :source_url, :relevance_score, :scraped_at
    )
    """
    params = {**lead, "scraped_at": lead.get("scraped_at") or datetime.now(timezone.utc).isoformat()}
    with _connect() as conn:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.rowcount > 0


def get_all_leads(min_score: int = 0) -> list[dict]:
    """Return all leads with relevance_score >= min_score, sorted descending."""
    sql = """
    SELECT * FROM leads
    WHERE relevance_score >= ?
    ORDER BY relevance_score DESC, scraped_at DESC
    """
    with _connect() as conn:
        rows = conn.execute(sql, (min_score,)).fetchall()
    return [dict(row) for row in rows]


def clear_db() -> None:
    """Drop and recreate the leads table (for dev/testing)."""
    with _connect() as conn:
        conn.execute("DROP TABLE IF EXISTS leads")
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()
