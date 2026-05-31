"""
BauNetz.de adapter — refactored from the original scraper.py.
Parses window.__INITIAL_STATE__ JSON (no JS rendering needed).
"""
import json
import re
import time
import hashlib
from pathlib import Path

import requests
from bs4 import BeautifulSoup

from sources.base import Source

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Multiple listing pages to rotate across — gives variety each run
LISTING_URLS = [
    "https://www.baunetz.de/projekte/index.html",
    "https://www.baunetz.de/projekte/wohnungsbau/index.html",
    "https://www.baunetz.de/projekte/buerogebaeude/index.html",
    "https://www.baunetz.de/projekte/hotel/index.html",
    "https://www.baunetz.de/projekte/kultur/index.html",
    "https://www.baunetz.de/projekte/bildung/index.html",
    "https://www.baunetz.de/projekte/mixed-use/index.html",
]

CACHE_DIR    = Path(".cache/baunetz")
CACHE_TTL_H  = 24        # hours before a cached page is considered stale
REQUEST_DELAY = 1.5


def _cache_path(url: str) -> Path:
    key = hashlib.md5(url.encode()).hexdigest()
    return CACHE_DIR / f"{key}.html"


def _is_stale(path: Path) -> bool:
    """Return True if file doesn't exist or is older than CACHE_TTL_H hours."""
    if not path.exists():
        return True
    age_h = (time.time() - path.stat().st_mtime) / 3600
    return age_h >= CACHE_TTL_H


def _fetch(url: str) -> str:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(url)
    if not _is_stale(path):
        return path.read_text(encoding="utf-8")
    time.sleep(REQUEST_DELAY)
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    html = resp.text
    path.write_text(html, encoding="utf-8")
    return html


def _parse_initial_state(html: str) -> dict:
    m = re.search(r"window\.__INITIAL_STATE__\s*=\s*", html)
    if not m:
        return {}
    try:
        state, _ = json.JSONDecoder().raw_decode(html, m.end())
        return state
    except Exception:
        return {}


def _teasers_from_url(listing_url: str) -> list[str]:
    """Fetch one listing page and return all project URLs found in it."""
    try:
        html  = _fetch(listing_url)
        state = _parse_initial_state(html)
        teasers = (
            state.get("nonPersistentStore", {})
                 .get("projekteIndex", {})
                 .get("teasers", [])
        )
        return [t["url"] for t in teasers if t.get("url")]
    except Exception:
        return []


class BauNetzSource(Source):
    name = "BauNetz.de"

    def get_project_urls(self, limit: int) -> list[str]:
        seen: set[str] = set()
        urls: list[str] = []

        for listing_url in LISTING_URLS:
            for url in _teasers_from_url(listing_url):
                if url not in seen:
                    seen.add(url)
                    urls.append(url)
            if len(urls) >= limit * 2:   # collect a healthy pool, then stop
                break

        return urls[:limit]

    def get_page_text(self, url: str) -> str:
        html  = _fetch(url)
        state = _parse_initial_state(html)
        detail = state.get("nonPersistentStore", {}).get("meldungDetail") or {}

        parts: list[str] = []
        if detail.get("headline"):
            parts.append(f"Titel: {detail['headline']}")
        if detail.get("subheadline"):
            parts.append(f"Untertitel: {detail['subheadline']}")

        offices = detail.get("offices") or []
        if offices:
            names = [o.get("name", "") for o in offices if o.get("name")]
            if names:
                parts.append(f"Architekturbüro: {', '.join(names)}")

        soup    = BeautifulSoup(html, "lxml")
        article = soup.select_one("article")
        if article:
            for tag in article.select("button, nav, .share, figcaption, .image-copyright"):
                tag.decompose()
            parts.append(article.get_text(separator="\n", strip=True))

        parts.append(f"\nSource URL: {url}")
        return "\n\n".join(parts)
