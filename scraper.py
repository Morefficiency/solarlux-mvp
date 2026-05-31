"""
Multi-source scraper runner.
Iterates over all registered Source adapters, collects URLs, fetches page
text, and tags each result with its source name.
Source failures are caught and logged — one bad source never stops the others.
"""
import difflib
import logging
import re
import unicodedata
from sources.registry import ALL_SOURCES

logger = logging.getLogger(__name__)


def fetch_all(limit_per_source: int = 15) -> list[dict]:
    """
    Run all sources and return list of:
        {"url": str, "text": str, "source": str}
    """
    results = []
    for source in ALL_SOURCES:
        try:
            urls = source.get_project_urls(limit=limit_per_source)
            logger.info("[%s] Got %d URLs", source.name, len(urls))
            for url in urls:
                try:
                    text = source.get_page_text(url)
                    results.append({"url": url, "text": text, "source": source.name})
                except Exception as e:
                    logger.warning("[%s] page fetch failed for %s: %s", source.name, url, e)
        except Exception as e:
            logger.warning("[%s] get_project_urls failed: %s", source.name, e)

    return results


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def _normalize(s: str) -> str:
    """Lowercase, strip accents, remove punctuation for fuzzy comparison."""
    s = s.lower().strip()
    s = "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9\s]", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def deduplicate(leads: list[dict]) -> list[dict]:
    """
    Fuzzy-deduplicate leads by (project_name, city).
    When two leads match (difflib ratio > 0.85), merge their source names.
    """
    unique: list[dict] = []

    for lead in leads:
        name_raw = lead.get("project_name") or ""
        city_raw = lead.get("city") or ""
        key = _normalize(name_raw + " " + city_raw)

        if not key.strip():
            unique.append(lead)
            continue

        matched = False
        for existing in unique:
            ex_name = existing.get("project_name") or ""
            ex_city = existing.get("city") or ""
            ex_key = _normalize(ex_name + " " + ex_city)

            ratio = difflib.SequenceMatcher(None, key, ex_key).ratio()
            if ratio > 0.85:
                # Merge sources
                existing_sources = existing.get("sources") or [existing.get("source", "")]
                new_source = lead.get("source", "")
                if new_source and new_source not in existing_sources:
                    existing_sources.append(new_source)
                existing["sources"] = existing_sources
                existing["source"] = ", ".join(existing_sources)
                matched = True
                break

        if not matched:
            lead.setdefault("sources", [lead.get("source", "")])
            unique.append(lead)

    return unique
