"""
Transparent relevance scoring for Solarlux leads (0–100).
Solarlux makes premium glass facades and sliding systems.
Best leads: multi-family residential, mixed-use, commercial — contacted via architect or GC.
Rules are intentionally simple and readable for slide presentation.
"""

# Project types that are strong Solarlux targets
HIGH_VALUE_TYPES = {
    "mehrfamilienhaus", "wohnbau", "wohngebäude", "wohnhaus",
    "mixed-use", "mixed use", "mischnutzung",
    "bürogebäude", "bürobau", "gewerbe", "gewerbebau",
    "hotel", "einzelhandel", "geschäftshaus", "wohn- und geschäftshaus",
}

# Types with moderate relevance
MEDIUM_VALUE_TYPES = {
    "umbau", "sanierung", "aufstockung", "umnutzung",
    "schule", "bildung", "kultur", "institutsbau",
}

# Types with low relevance for Solarlux
LOW_VALUE_TYPES = {
    "einfamilienhaus", "villa", "stallgebäude", "stall", "sportanlage",
    "infrastruktur", "brücke", "parkhaus",
}


def score_lead(lead: dict) -> int:
    """
    Score a lead 0–100 based on Solarlux sales relevance.
    Higher = better fit for premium glass facades / sliding systems.
    """
    score = 0
    project_type = (lead.get("project_type") or "").lower().strip()

    # Base score by project type — biggest single factor
    if any(t in project_type for t in HIGH_VALUE_TYPES):
        score += 45  # strong commercial/residential target
    elif any(t in project_type for t in MEDIUM_VALUE_TYPES):
        score += 25  # possible but lower priority
    elif any(t in project_type for t in LOW_VALUE_TYPES):
        score += 5   # rarely relevant for glass facades
    else:
        score += 15  # unknown type — neutral starting point

    # German project bonus — Solarlux primarily serves DACH market
    bundesland = (lead.get("bundesland") or "").strip()
    if bundesland:
        score += 20  # confirmed German project = in Solarlux's primary market

    # Architect identified — enables direct sales contact
    architect = (lead.get("architect_firm") or "").strip()
    if architect:
        score += 15  # known architect = actionable contact

    # Bauherr identified — additional stakeholder for follow-up
    bauherr = (lead.get("bauherr") or "").strip()
    if bauherr:
        score += 10  # known client = richer lead profile

    # Scale bonus — larger projects buy more facade/glazing systems
    scale_raw = (lead.get("scale_units_or_sqm") or "").lower()
    scale_num = _extract_number(scale_raw)
    if "m²" in scale_raw or "sqm" in scale_raw or "m2" in scale_raw:
        if scale_num and scale_num >= 2000:
            score += 10  # large footprint = significant glazing budget
        elif scale_num and scale_num >= 500:
            score += 5   # medium scale — still worthwhile
    elif "wohneinheit" in scale_raw or "einheit" in scale_raw or "wohnung" in scale_raw:
        if scale_num and scale_num >= 20:
            score += 10  # 20+ units = multi-family = good Solarlux customer
        elif scale_num and scale_num >= 8:
            score += 5   # smaller multi-family

    return min(score, 100)  # cap at 100


def _extract_number(text: str) -> float | None:
    """Extract the first numeric value from a string."""
    import re
    text = text.replace(".", "").replace(",", ".")  # handle German number format
    m = re.search(r"[\d]+(?:\.\d+)?", text)
    if m:
        try:
            return float(m.group())
        except ValueError:
            return None
    return None
