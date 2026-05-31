"""
Competitionline.com adapter — architecture competition results.
Note: full competition listings require a paid subscription.
This adapter scrapes the publicly visible ergebnisse page.
Returns empty gracefully when content is behind a paywall.
"""
import logging
import time
import hashlib
from pathlib import Path

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
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

BASE_URL = "https://www.competitionline.com"
LISTING_URL = f"{BASE_URL}/de/news/ergebnisse"
CACHE_DIR = Path(".cache/competitionline")
REQUEST_DELAY = 1.5

PAYWALL_SIGNALS = ["mitglied-werden", "Mitglied werden", "Login für Mitglieder", "anmelden"]


def _cache_path(url: str) -> Path:
    key = hashlib.md5(url.encode()).hexdigest()
    return CACHE_DIR / f"{key}.html"


def _fetch(url: str, use_cache: bool = True) -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(url)
    if use_cache and path.exists():
        return path.read_text(encoding="utf-8")
    time.sleep(REQUEST_DELAY)
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    html = resp.text
    path.write_text(html, encoding="utf-8")
    return html


class CompetitionlineSource(Source):
    name = "competitionline.com"

    def get_project_urls(self, limit: int) -> list[str]:
        try:
            html = _fetch(LISTING_URL)
        except Exception as e:
            logger.warning("[competitionline] Fetch failed: %s", e)
            return []

        # Detect paywall
        if any(s in html for s in PAYWALL_SIGNALS):
            logger.warning(
                "[competitionline] Content behind paywall/login — "
                "subscribe at competitionline.com for full access. Returning 0 URLs."
            )

        # Try to find competition detail links anyway
        soup = BeautifulSoup(html, "lxml")
        links = []
        EXCLUDE = ["/erstellen/", "/suche", "/anmelden", "/mitglied", "melden"]
        for a in soup.find_all("a", href=True):
            href = a.get("href", "")
            # Only accept actual competition result/project pages
            if not any(p in href for p in ["/de/ergebnis/", "/de/wettbewerb/", "/de/news/"]):
                continue
            if any(ex in href for ex in EXCLUDE):
                continue
            full = (href if href.startswith("http") else BASE_URL + href).strip()
            if "\n" not in full and len(full) < 300:
                links.append(full)

        if not links:
            logger.warning("[competitionline] No accessible competition URLs found (paywall active).")
        return list(dict.fromkeys(links))[:limit]

    def get_page_text(self, url: str) -> str:
        try:
            html = _fetch(url)
        except Exception as e:
            logger.warning("[competitionline] Page fetch failed for %s: %s", url, e)
            return ""
        soup = BeautifulSoup(html, "lxml")
        main = soup.select_one("main") or soup.select_one("article") or soup.body
        text = main.get_text(separator="\n", strip=True) if main else ""
        return f"{text}\n\nSource URL: {url}"
