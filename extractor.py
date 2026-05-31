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
- project_type: Projekttyp, z.B. Mehrfamilienhaus, Wohnbau, Mixed-Use, Bürogebäude, Hotel, Schule, Gewerbe, Umbau, Architekturbüro, etc. (string oder null)
- architect_firm: Name des Architekturbüros (string oder null)
- bauherr: Name des Bauherrn / Investors / Auftraggebers (string oder null)
- estimated_completion: Geschätztes Fertigstellungsjahr oder Zeitraum (string oder null)
- scale_units_or_sqm: Anzahl Wohneinheiten ODER Bruttofläche in m² (string oder null)
- source_url: Die Quell-URL (string oder null)
- actors: Liste aller identifizierbaren Akteure im Projekt. Jeder Eintrag hat:
    - name: Vollständiger Name der Person oder Firma (string)
    - role: Eine von: "Architekt", "Planer", "Generalunternehmer", "Projektentwickler", "Unknown"
    - firm: Firmenzugehörigkeit falls angegeben (string oder null)
    - email: E-Mail-Adresse falls im Text genannt (string oder null)
    - phone: Telefonnummer falls im Text genannt (string oder null)
  Keine Akteure gefunden → leere Liste [].

Antworte ausschließlich mit dem JSON-Objekt.

TEXT:
{page_text}"""

REQUIRED_FIELDS = [
    "project_name", "city", "bundesland", "project_type",
    "architect_firm", "bauherr", "estimated_completion",
    "scale_units_or_sqm", "source_url", "actors",
]


def _call_llm(page_text: str) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    client = anthropic.Anthropic(api_key=api_key)
    prompt = EXTRACT_PROMPT.format(page_text=page_text[:6000])

    message = client.messages.create(
        model=MODEL,
        max_tokens=768,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def _parse_response(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text)


def extract_lead(page_text: str) -> dict:
    """
    Extract structured lead data from raw project page text.
    Retries once on JSON parse failure. Returns dict with all REQUIRED_FIELDS.
    """
    for attempt in range(2):
        try:
            raw = _call_llm(page_text)
            data = _parse_response(raw)
            for field in REQUIRED_FIELDS:
                data.setdefault(field, None)
            # Ensure actors is always a list
            if not isinstance(data.get("actors"), list):
                data["actors"] = []
            return data
        except json.JSONDecodeError as e:
            if attempt == 0:
                logger.warning("JSON parse failed (attempt 1), retrying: %s", e)
            else:
                logger.warning("JSON parse failed (attempt 2), skipping. Raw: %s", raw[:200])
                return {f: ([] if f == "actors" else None) for f in REQUIRED_FIELDS}
        except Exception as e:
            logger.error("LLM extraction error: %s", e)
            return {f: ([] if f == "actors" else None) for f in REQUIRED_FIELDS}

    return {f: ([] if f == "actors" else None) for f in REQUIRED_FIELDS}
