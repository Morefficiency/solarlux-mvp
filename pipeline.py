"""
End-to-end pipeline: multi-source scrape -> extract -> score -> deduplicate -> store.
"""
import logging
from datetime import datetime, timezone

from scraper import fetch_all, deduplicate
from extractor import extract_lead
from scorer import score_lead
from db import init_db, insert_lead, get_all_leads

logger = logging.getLogger(__name__)


def run_pipeline(limit_per_source: int = 15) -> list[dict]:
    """
    Run the full pipeline across all registered sources.
    Returns list of processed leads (including duplicates skipped by DB).
    """
    init_db()

    # Step 1: fetch raw page texts from all sources
    raw_pages = fetch_all(limit_per_source=limit_per_source)
    logger.info("Total pages fetched: %d", len(raw_pages))

    # Step 2: extract + score each page
    leads = []
    for i, page in enumerate(raw_pages):
        logger.info("[%d/%d] Extracting: %s", i + 1, len(raw_pages), page["url"][:80])
        try:
            lead = extract_lead(page["text"])
            lead["source_url"] = lead.get("source_url") or page["url"]
            lead["source"] = page["source"]
            lead["relevance_score"] = score_lead(lead)
            lead["scraped_at"] = datetime.now(timezone.utc).isoformat()
            leads.append(lead)
            logger.info(
                "  Score: %d | Source: %s | %s",
                lead["relevance_score"], lead["source"], lead.get("project_name"),
            )
        except Exception as e:
            logger.error("  Extraction failed for %s: %s", page["url"], e)

    # Step 3: deduplicate across sources
    leads = deduplicate(leads)
    logger.info("After dedup: %d unique leads", len(leads))

    # Step 4: store
    for lead in leads:
        try:
            insert_lead(lead)
        except Exception as e:
            logger.error("DB insert failed: %s", e)

    return leads
