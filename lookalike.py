"""
Digitale Zwillinge — lookalike matching against a reference firm profile.
Scores each lead vs. the reference with transparent, readable rules.
"""

REFERENCE_FIRM = {
    "firm_name": "Mustermann Architekten GmbH",
    "city": "Hamburg",
    "bundesland": "Hamburg",
    "project_type": "Mehrfamilienhaus",
    "typical_scale": "20-50 units",
}

HIGH_VALUE_TYPES = {
    "mehrfamilienhaus", "wohnbau", "wohngebäude", "wohnhaus",
    "mixed-use", "mixed use", "mischnutzung",
    "wohn- und geschäftshaus", "geschäftshaus",
}


def _type_match(ref_type: str, lead_type: str | None) -> bool:
    if not lead_type:
        return False
    r = ref_type.lower()
    l = lead_type.lower()
    return r in l or l in r or any(t in l for t in HIGH_VALUE_TYPES)


def _scale_overlap(typical: str, lead_scale: str | None) -> bool:
    """Return True if lead scale plausibly overlaps with reference typical scale."""
    if not lead_scale:
        return False
    import re
    nums = [int(n) for n in re.findall(r"\d+", typical)]
    lead_nums = [int(n) for n in re.findall(r"\d+", lead_scale)]
    if not nums or not lead_nums:
        return False
    ref_min, ref_max = min(nums), max(nums)
    lead_val = lead_nums[0]
    # Allow ±50 % overlap
    return lead_val >= ref_min * 0.5 and lead_val <= ref_max * 2.0


def _has_architect_actor(actors: list) -> bool:
    if not actors:
        return False
    return any(
        str(a.get("role", "")).lower() in ("architekt", "planer")
        for a in actors
    )


def _match_reason(scores: dict) -> str:
    reasons = []
    if scores.get("type"):
        reasons.append("gleicher Projekttyp")
    if scores.get("bundesland"):
        reasons.append("gleiches Bundesland")
    if scores.get("scale"):
        reasons.append("ähnliches Projektvolumen")
    if scores.get("actor"):
        reasons.append("Architekt identifiziert")
    return " · ".join(reasons) if reasons else "grundlegende Übereinstimmung"


def score_lookalike(reference: dict, lead: dict) -> tuple[int, str]:
    """
    Score a lead against the reference firm. Returns (score, reason_string).
    Max score = 100.
    """
    breakdown = {}

    # +30 project_type match
    if _type_match(reference.get("project_type", ""), lead.get("project_type")):
        breakdown["type"] = 30

    # +25 bundesland match
    ref_bl = (reference.get("bundesland") or "").strip().lower()
    lead_bl = (lead.get("bundesland") or "").strip().lower()
    if ref_bl and lead_bl and ref_bl == lead_bl:
        breakdown["bundesland"] = 25

    # +20 scale overlap
    if _scale_overlap(reference.get("typical_scale", ""), lead.get("scale_units_or_sqm")):
        breakdown["scale"] = 20

    # +25 any actor with Architekt role
    actors = lead.get("actors") or []
    if isinstance(actors, list) and _has_architect_actor(actors):
        breakdown["actor"] = 25

    total = min(sum(breakdown.values()), 100)
    return total, _match_reason(breakdown)


def find_lookalikes(
    reference: dict,
    all_leads: list[dict],
    top_n: int = 3,
) -> list[dict]:
    """
    Score every lead against the reference firm profile and return
    the top_n matches sorted by match score descending.
    Each returned dict includes 'match_score' and 'match_reason'.
    """
    scored = []
    for lead in all_leads:
        ms, reason = score_lookalike(reference, lead)
        if ms > 0:
            entry = {**lead, "match_score": ms, "match_reason": reason}
            scored.append(entry)

    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return scored[:top_n]
