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

INDEX_URL = "https://www.architektensuche.de/"
BASE_URL  = "https://www.architektensuche.de"
CACHE_DIR = Path(".cache/architektensuche")
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


def _fetch_index(use_cache: bool = True) -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(INDEX_URL)
    if use_cache and path.exists():
        return path.read_text(encoding="utf-8")
    time.sleep(REQUEST_DELAY)
    resp = requests.get(INDEX_URL, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    html = resp.text
    path.write_text(html, encoding="utf-8")
    return html


def _parse_city(raw: str) -> tuple[str, str | None]:
    """Extract city and bundesland from raw link text like 'FirmName D-60329 Frankfurt'."""
    # Try to find city after postcode pattern: D-XXXXX or just 5-digit PLZ
    m = re.search(r"(?:D-)?(\d{5})\s+([A-ZÄÖÜa-zäöü][A-ZÄÖÜa-zäöü\s\-]+?)(?:\s*$|\s+\d)", raw)
    if m:
        city = m.group(2).strip()
        bundesland = CITY_TO_BL.get(city.lower())
        return city, bundesland
    # Fallback: last word(s) that look like a city
    parts = raw.rsplit(None, 1)
    if len(parts) == 2 and parts[1][0].isupper():
        city = parts[1]
        return city, CITY_TO_BL.get(city.lower())
    return "", None


def _extract_firms(html: str, limit: int) -> list[dict]:
    """Parse index page and extract firm name + city from link text."""
    soup = BeautifulSoup(html, "lxml")
    firms = []
    seen = set()

    for a in soup.find_all("a", href=True):
        href = a.get("href", "")
        # Only relative firm profile links: /firm-slug/numeric-id
        if not re.match(r"^/[a-z0-9\-]+/\d+$", href):
            continue
        raw_text = a.get_text(strip=True)
        if not raw_text or href in seen:
            continue
        seen.add(href)

        # Split firm name from location info
        # Link text format: "FirmNameD-60329 Frankfurt" or "Firm Name69115 Heidelberg"
        name_match = re.match(r"^(.*?)(?:D-\d{5}|\d{5})", raw_text)
        firm_name = name_match.group(1).strip() if name_match else raw_text
        city, bundesland = _parse_city(raw_text)

        firms.append({
            "url": BASE_URL + href,
            "firm_name": firm_name or raw_text,
            "city": city,
            "bundesland": bundesland,
        })

        if len(firms) >= limit:
            break

    return firms


class ArchitektenSucheSource(Source):
    name = "architektensuche.de"

    def __init__(self):
        self._firms: list[dict] = []  # cached after first call

    def get_project_urls(self, limit: int) -> list[str]:
        try:
            html = _fetch_index()
            self._firms = _extract_firms(html, limit)
            if not self._firms:
                logger.warning("[architektensuche] No firm links found on index page.")
                return []
            return [f["url"] for f in self._firms]
        except Exception as e:
            logger.warning("[architektensuche] Index fetch failed: %s", e)
            return []

    def get_page_text(self, url: str) -> str:
        """
        Firm profile pages redirect to a JS SPA — not scrapable with requests.
        Instead, synthesize structured text from what we know about the firm
        (harvested from the index page link text).
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
