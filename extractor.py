"""
LLM-based lead extraction using Claude Haiku.
Single swappable extract_lead() function → returns structured dict.
"""
import json
import logging
import os

import anthropic

logger = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """Du bist ein Datenextraktions-Assistent für Bauprojekte.
Analysiere den folgenden Text eines Bauprojekts und extrahiere die geforderten Informationen.
Antworte NUR mit einem validen JSON-Objekt — kein Text davor oder danach, keine Markdown-Code-Blöcke.
Fehlende Werte müssen als null angegeben werden."""

EXTRACT_PROMPT = """Extrahiere aus dem folgenden Bauprojekt-Text diese Felder als JSON:

- project_name: Name/Bezeichnung des Projekts (string oder null)
- city: Stadt des Projekts (string oder null)
- bundesland: Deutsches Bundesland (string oder null; null wenn nicht in Deutschland)
- project_type: Projekttyp, z.B. Mehrfamilienhaus, Wohnbau, Mixed-Use, Bürogebäude, Hotel, Schule, Gewerbe, Umbau, etc. (string oder null)
- architect_firm: Name des Architekturbüros (string oder null)
- bauherr: Name des Bauherrn / Investors / Auftraggebers (string oder null)
- estimated_completion: Geschätztes Fertigstellungsjahr oder Zeitraum (string oder null)
- scale_units_or_sqm: Anzahl Wohneinheiten ODER Bruttofläche in m² (string oder null)
- source_url: Die Quell-URL (string oder null)

Antworte ausschließlich mit dem JSON-Objekt.

TEXT:
{page_text}"""

REQUIRED_FIELDS = [
    "project_name", "city", "bundesland", "project_type",
    "architect_firm", "bauherr", "estimated_completion",
    "scale_units_or_sqm", "source_url",
]


def _call_llm(page_text: str) -> str:
    """Call Claude Haiku and return the raw text response."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    client = anthropic.Anthropic(api_key=api_key)
    prompt = EXTRACT_PROMPT.format(page_text=page_text[:6000])  # cap tokens

    message = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def _parse_response(raw: str) -> dict:
    """Parse JSON from LLM response, stripping accidental markdown fences."""
    text = raw.strip()
    # Strip ```json ... ``` if present
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


def extract_lead(page_text: str) -> dict:
    """
    Extract structured lead data from raw project page text.
    Retries once on JSON parse failure. Returns dict with all REQUIRED_FIELDS
    (missing values are None).
    """
    for attempt in range(2):
        try:
            raw = _call_llm(page_text)
            data = _parse_response(raw)
            # Ensure all required fields present (fill missing with None)
            for field in REQUIRED_FIELDS:
                data.setdefault(field, None)
            return data
        except json.JSONDecodeError as e:
            if attempt == 0:
                logger.warning("JSON parse failed (attempt 1), retrying: %s", e)
            else:
                logger.warning("JSON parse failed (attempt 2), skipping. Raw: %s", raw[:200])
                return {f: None for f in REQUIRED_FIELDS}
        except Exception as e:
            logger.error("LLM extraction error: %s", e)
            return {f: None for f in REQUIRED_FIELDS}

    return {f: None for f in REQUIRED_FIELDS}


# ---------------------------------------------------------------------------
# CHECKPOINT
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    from scraper import fetch_project_list, fetch_project_page

    logging.basicConfig(level=logging.INFO)
    print("=== CHECKPOINT: extractor.py ===\n")

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: Set ANTHROPIC_API_KEY environment variable first.")
        sys.exit(1)

    urls = fetch_project_list(limit=15)
    # Pick a German project for a more interesting result
    german_urls = [u for u in urls if any(
        kw in u for kw in ["Berlin", "Muenchen", "Frankfurt", "Hamburg",
                           "Tirschenreuth", "Deutschland", "Umbau"]
    )]
    test_url = german_urls[0] if german_urls else urls[0]

    print(f"Using URL: {test_url}")
    page_text = fetch_project_page(test_url)
    print(f"Page text length: {len(page_text)} chars\n")

    lead = extract_lead(page_text)
    print("Extracted lead:")
    print(json.dumps(lead, ensure_ascii=False, indent=2))
