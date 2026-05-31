"""
Architektensuche.de adapter — German architect firm directory.

The firm profile pages redirect to a JS SPA (baunetz-architekten.de) which
can't be scraped with requests. Instead this adapter harvests firm names and
cities directly from the index page link text and synthesizes structured
page text that the LLM extractor can process into actor/contact leads.

Each "lead" represents an architect firm — useful to Solarlux for contact
targeting even without a specific project URL.
"""
import logging
import random
import re
import time
from pathlib import Path
import hashlib

import requests
from bs4 import BeautifulSoup

from sources.base import Source

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9",
}

INDEX_URL    = "https://www.architektensuche.de/"
BASE_URL     = "https://www.architektensuche.de"
CACHE_DIR    = Path(".cache/architektensuche")
CACHE_TTL_H  = 24        # hours before the index page is re-fetched
REQUEST_DELAY = 1.5

# German city → Bundesland mapping for common cities
CITY_TO_BL: dict[str, str] = {
    "berlin": "Berlin", "hamburg": "Hamburg", "münchen": "Bayern",
    "muenchen": "Bayern", "munich": "Bayern", "köln": "Nordrhein-Westfalen",
    "koeln": "Nordrhein-Westfalen", "frankfurt": "Hessen",
    "stuttgart": "Baden-Württemberg", "düsseldorf": "Nordrhein-Westfalen",
    "dortmund": "Nordrhein-Westfalen", "essen": "Nordrhein-Westfalen",
    "leipzig": "Sachsen", "bremen": "Bremen", "dresden": "Sachsen",
    "hannover": "Niedersachsen", "nürnberg": "Bayern", "nuernberg": "Bayern",
    "duisburg": "Nordrhein-Westfalen", "bochum": "Nordrhein-Westfalen",
    "wuppertal": "Nordrhein-Westfalen", "bielefeld": "Nordrhein-Westfalen",
    "bonn": "Nordrhein-Westfalen", "münster": "Nordrhein-Westfalen",
    "freiburg": "Baden-Württemberg", "augsburg": "Bayern",
    "heidelberg": "Baden-Württemberg", "karlsruhe": "Baden-Württemberg",
    "mannheim": "Baden-Württemberg", "mainz": "Rheinland-Pfalz",
    "wiesbaden": "Hessen", "kassel": "Hessen", "erfurt": "Thüringen",
    "rostock": "Mecklenburg-Vorpommern", "kiel": "Schleswig-Holstein",
    "saarbrücken": "Saarland", "potsdam": "Brandenburg",
    "aachen": "Nordrhein-Westfalen", "magdeburg": "Sachsen-Anhalt",
}


def _cache_path(url: str) -> Path:
    key = hashlib.md5(url.encode()).hexdigest()
    return CACHE_DIR / f"{key}.html"


def _is_stale(path: Path) -> bool:
    """Return True if file doesn't exist or is older than CACHE_TTL_H hours."""
    if not path.exists():
        return True
    age_h = (time.time() - path.stat().st_mtime) / 3600
    return age_h >= CACHE_TTL_H


def _fetch_index() -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(INDEX_URL)
    if not _is_stale(path):
        return path.read_text(encoding="utf-8")
    time.sleep(REQUEST_DELAY)
    resp = requests.get(INDEX_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    html = resp.text
    path.write_text(html, encoding="utf-8")
    return html


def _parse_city(raw: str) -> tuple[str, str | None]:
    """Extract city and bundesland from raw link text like 'FirmName D-60329 Frankfurt'."""
    m = re.search(r"(?:D-)?(\d{5})\s+([A-ZÄÖÜa-zäöü][A-ZÄÖÜa-zäöü\s\-]+?)(?:\s*$|\s+\d)", raw)
    if m:
        city = m.group(2).strip()
        bundesland = CITY_TO_BL.get(city.lower())
        return city, bundesland
    parts = raw.rsplit(None, 1)
    if len(parts) == 2 and parts[1][0].isupper():
        city = parts[1]
        return city, CITY_TO_BL.get(city.lower())
    return "", None


def _extract_all_firms(html: str) -> list[dict]:
    """Parse ALL firms from the index page (no limit — caller decides how many to use)."""
    soup  = BeautifulSoup(html, "lxml")
    firms = []
    seen  = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        if not re.match(r"^/[a-z0-9\-]+/\d+$", href):
            continue
        raw_text = a.get_text(strip=True)
        if not raw_text or href in seen:
            continue
        seen.add(href)

        name_match = re.match(r"^(.*?)(?:D-\d{5}|\d{5})", raw_text)
        firm_name  = name_match.group(1).strip() if name_match else raw_text
        city, bundesland = _parse_city(raw_text)

        firms.append({
            "url":       BASE_URL + href,
            "firm_name": firm_name or raw_text,
            "city":      city,
            "bundesland": bundesland,
        })

    return firms


class ArchitektenSucheSource(Source):
    name = "architektensuche.de"

    def __init__(self):
        self._firms: list[dict] = []

    def get_project_urls(self, limit: int) -> list[str]:
        try:
            html      = _fetch_index()
            all_firms = _extract_all_firms(html)
            if not all_firms:
                logger.warning("[architektensuche] No firm links found on index page.")
                return []

            # Randomly sample `limit` firms from the full pool (~700+ firms)
            # so each scrape run targets a different set of offices.
            sampled = random.sample(all_firms, min(limit, len(all_firms)))
            self._firms = sampled
            logger.info("[architektensuche] Sampled %d / %d firms", len(sampled), len(all_firms))
            return [f["url"] for f in sampled]
        except Exception as e:
            logger.warning("[architektensuche] Index fetch failed: %s", e)
            return []

    def get_page_text(self, url: str) -> str:
        """
        Firm profile pages redirect to a JS SPA — not scrapable with requests.
        Synthesize structured text from what we harvested on the index page.
        """
        firm = next((f for f in self._firms if f["url"] == url), None)
        if not firm:
            logger.warning("[architektensuche] No cached firm data for %s", url)
            return f"Source URL: {url}"

        parts = [
            f"Projektname: {firm['firm_name']} – Büroprofil",
            f"Architekturbüro: {firm['firm_name']}",
            f"Projekttyp: Architekturbüro (Kontaktlead)",
        ]
        if firm["city"]:
            parts.append(f"Stadt: {firm['city']}")
        if firm["bundesland"]:
            parts.append(f"Bundesland: {firm['bundesland']}")
        parts.append(
            "Hinweis: Dieses Büro ist im deutschen Architektenverzeichnis gelistet "
            "und ein potenzieller Solarlux-Kontakt für zukünftige Projekte."
        )
        parts.append(f"\nSource URL: {url}")
        return "\n".join(parts)
