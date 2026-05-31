"""
End-to-end pipeline: scrape -> extract -> score -> store.
Can be run standalone (checkpoint) or called from app.py.
"""
import json
import logging
import time
from datetime import datetime, timezone

from scraper import fetch_project_list, fetch_project_page
from extractor import extract_lead
from scorer import score_lead
from db import init_db, insert_lead, get_all_leads

logger = logging.getLogger(__name__)


def run_pipeline(limit: int = 15) -> list[dict]:
    """
    Run the full scrape -> extract -> score -> store pipeline.
    Returns list of leads that were successfully processed.
    """
    init_db()
    urls = fetch_project_list(limit=limit)
    logger.info("Fetched %d project URLs", len(urls))

    results = []
    for i, url in enumerate(urls):
        logger.info("[%d/%d] Processing: %s", i + 1, len(urls), url)
        try:
            page_text = fetch_project_page(url)
            lead = extract_lead(page_text)
            lead["source_url"] = lead.get("source_url") or url
            lead["relevance_score"] = score_lead(lead)
            lead["scraped_at"] = datetime.now(timezone.utc).isoformat()

            inserted = insert_lead(lead)
            status = "inserted" if inserted else "duplicate"
            logger.info("  Score: %d | %s | %s", lead["relevance_score"], status, lead.get("project_name"))
            results.append(lead)
        except Exception as e:
            logger.error("  Failed for %s: %s", url, e)

    return results


# ---------------------------------------------------------------------------
# CHECKPOINT — run one lead through the full pipeline
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys, os
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: Set ANTHROPIC_API_KEY environment variable first.")
        sys.exit(1)

    print("=== CHECKPOINT: end-to-end pipeline (1 lead) ===\n")

    init_db()

    # Fetch just the first URL
    from scraper import fetch_project_list, fetch_project_page
    from extractor import extract_lead
    from scorer import score_lead
    from db import insert_lead, get_all_leads, clear_db

    # Fresh start for checkpoint
    clear_db()

    urls = fetch_project_list(limit=15)
    # Prefer a German project
    german = [u for u in urls if any(k in u for k in
              ["Berlin", "Muenchen", "Frankfurt", "Tirschenreuth", "Hamburg",
               "Umbau", "Institutsbau", "Aufstockung"])]
    url = german[0] if german else urls[0]

    print(f"Step 1 — Scraping: {url}")
    page_text = fetch_project_page(url)
    print(f"          Got {len(page_text)} chars of text\n")

    print("Step 2 — Extracting with LLM...")
    lead = extract_lead(page_text)
    lead["source_url"] = lead.get("source_url") or url
    print(f"          Extracted: {json.dumps(lead, ensure_ascii=False, indent=2)}\n")

    print("Step 3 — Scoring...")
    lead["relevance_score"] = score_lead(lead)
    print(f"          Score: {lead['relevance_score']}/100\n")

    print("Step 4 — Storing in SQLite...")
    lead["scraped_at"] = datetime.now(timezone.utc).isoformat()
    inserted = insert_lead(lead)
    print(f"          Inserted: {inserted}\n")

    print("Step 5 — Reading back from DB...")
    all_leads = get_all_leads(min_score=0)
    print(f"          Leads in DB: {len(all_leads)}")
    if all_leads:
        row = all_leads[0]
        print(f"          First row: project_name={row['project_name']!r}, "
              f"city={row['city']!r}, score={row['relevance_score']}")

    print("\n=== CHECKPOINT PASSED ===")
