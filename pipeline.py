"""
End-to-end pipeline: multi-source scrape -> extract -> score -> upsert -> trim.
The DB is the persistent cache — never wiped automatically.
"""
import logging
from datetime import datetime, timezone

from scraper import fetch_all, deduplicate
from extractor import extract_lead
from scorer import score_lead
from db import init_db, upsert_lead, auto_trim, get_cache_stats

logger = logging.getLogger(__name__)


def run_pipeline(limit_per_source: int = 15) -> dict:
    """
    Run the full pipeline across all registered sources.
    Returns summary dict: {processed, inserted, updated, evicted, cache_stats}
    """
    init_db()

    # Step 1: fetch raw page texts from all sources
    raw_pages = fetch_all(limit_per_source=limit_per_source)
    logger.info("Total pages fetched: %d", len(raw_pages))

    # Step 2: extract + score
    leads = []
    for i, page in enumerate(raw_pages):
        logger.info("[%d/%d] Extracting: %s", i + 1, len(raw_pages), page["url"][:80])
        try:
            lead = extract_lead(page["text"])
            lead["source_url"] = lead.get("source_url") or page["url"]
            lead["source"]     = page["source"]
            lead["relevance_score"] = score_lead(lead)
            lead["scraped_at"] = datetime.now(timezone.utc).isoformat()
            leads.append(lead)
            logger.info("  Score: %d | %s | %s",
                        lead["relevance_score"], lead["source"], lead.get("project_name"))
        except Exception as e:
            logger.error("  Extraction failed for %s: %s", page["url"], e)

    # Step 3: within-run dedup (same URL or very similar name+city from different sources)
    leads = deduplicate(leads)
    logger.info("After within-run dedup: %d leads", len(leads))

    # Step 4: upsert into persistent cache
    inserted = updated = 0
    for lead in leads:
        try:
            result = upsert_lead(lead)
            if result == "inserted":
                inserted += 1
            elif result == "updated":
                updated += 1
        except Exception as e:
            logger.error("DB upsert failed for %s: %s", lead.get("source_url"), e)

    logger.info("Upserted: %d new, %d updated", inserted, updated)

    # Step 5: auto-trim if over cap
    evicted = auto_trim()

    stats = get_cache_stats()
    return {
        "processed": len(leads),
        "inserted":  inserted,
        "updated":   updated,
        "evicted":   evicted,
        "cache_stats": stats,
    }
