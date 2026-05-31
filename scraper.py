"""
Scraper for BauNetz.de project pages.
Uses __INITIAL_STATE__ JSON embedded in each page — no JS rendering needed.
"""
import json
import re
import time
import hashlib
import os
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

LISTING_URL = "https://www.baunetz.de/projekte/index.html"
CACHE_DIR = Path(".cache")
REQUEST_DELAY = 1.5  # seconds between requests


def _cache_path(url: str) -> Path:
    key = hashlib.md5(url.encode()).hexdigest()
    return CACHE_DIR / f"{key}.html"


def _fetch(url: str, use_cache: bool = True) -> str:
    """Fetch URL with disk caching and User-Agent spoofing."""
    CACHE_DIR.mkdir(exist_ok=True)
    path = _cache_path(url)

    if use_cache and path.exists():
        return path.read_text(encoding="utf-8")

    time.sleep(REQUEST_DELAY)
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    html = resp.text
    path.write_text(html, encoding="utf-8")
    return html


def _parse_initial_state(html: str) -> dict:
    """Extract and parse window.__INITIAL_STATE__ JSON from page HTML."""
    m = re.search(r"window\.__INITIAL_STATE__\s*=\s*", html)
    if not m:
        return {}
    try:
        state, _ = json.JSONDecoder().raw_decode(html, m.end())
        return state
    except Exception:
        return {}


def fetch_project_list(limit: int = 15) -> list[str]:
    """
    Fetch BauNetz.de project listing and return up to `limit` project URLs.
    """
    html = _fetch(LISTING_URL)
    state = _parse_initial_state(html)
    teasers = (
        state.get("nonPersistentStore", {})
             .get("projekteIndex", {})
             .get("teasers", [])
    )
    urls = [t["url"] for t in teasers if t.get("url")]
    return urls[:limit]


def fetch_project_page(url: str) -> str:
    """
    Fetch a BauNetz.de project detail page and return cleaned text.

    Combines:
    - Structured fields from __INITIAL_STATE__ (headline, subheadline, offices)
    - Body text from the <article> HTML element
    """
    html = _fetch(url)
    state = _parse_initial_state(html)
    detail = state.get("nonPersistentStore", {}).get("meldungDetail") or {}

    parts: list[str] = []

    # Structured metadata available directly
    if detail.get("headline"):
        parts.append(f"Titel: {detail['headline']}")
    if detail.get("subheadline"):
        parts.append(f"Untertitel: {detail['subheadline']}")

    # Architect / office info
    offices = detail.get("offices") or []
    if offices:
        names = [o.get("name", "") for o in offices if o.get("name")]
        if names:
            parts.append(f"Architekturbüro: {', '.join(names)}")

    # Article body text
    soup = BeautifulSoup(html, "lxml")
    article = soup.select_one("article")
    if article:
        # Remove nav / share / image-caption noise
        for tag in article.select("button, nav, .share, figcaption, .image-copyright"):
            tag.decompose()
        body_text = article.get_text(separator="\n", strip=True)
        parts.append(body_text)

    # Append the source URL so the LLM can reference it
    parts.append(f"\nSource URL: {url}")

    return "\n\n".join(parts)


# ---------------------------------------------------------------------------
# CHECKPOINT helper — run this file directly to verify
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("=== CHECKPOINT: scraper.py ===\n")

    print("Fetching project list...")
    urls = fetch_project_list(limit=15)
    print(f"Found {len(urls)} project URLs:")
    for u in urls:
        print(f"  {u}")

    if not urls:
        print("ERROR: No URLs returned. Check network / BauNetz URL.")
    else:
        print(f"\nFetching first project: {urls[0]}")
        text = fetch_project_page(urls[0])
        print("\n--- Cleaned text (first 800 chars) ---")
        print(text[:800])
        print(f"\n[Total length: {len(text)} chars]")
