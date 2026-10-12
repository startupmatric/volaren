"""
Tools for the LangGraph portfolio agent.

Design principle: the LLM NEVER calculates numbers.
All numeric facts come from the deterministic services in
attribution_service and explain_service. The LLM only writes prose
based on evidence we hand it.

This file has three jobs:
  1. gather_evidence()       -> structured facts for the LLM
  2. validate_numbers()      -> reject any number the LLM invented
  3. build_fallback()        -> deterministic text if the LLM fails
"""

import re
from typing import Optional

from sqlalchemy.orm import Session

from app.services.attribution_service import (
    get_movers,
    get_sector_attribution,
)
from app.services.explain_service import explain_attribution


# =========================================================
# EVIDENCE GATHERING
# =========================================================

def gather_evidence(
    db: Session,
    portfolio_id: int,
) -> Optional[dict]:
    """
    Build a compact, structured evidence dict for the LLM.

    Returns None if the portfolio has no snapshots.
    """

    movers = get_movers(db, portfolio_id)

    if movers is None:
        return None

    attribution = get_sector_attribution(db, portfolio_id)

    deterministic = explain_attribution(db, portfolio_id)

    contributors = movers.get("top_contributors") or []
    detractors = movers.get("top_detractors") or []
    sectors = (attribution or {}).get("sectors") or []

    top_contributor = contributors[0] if contributors else None
    top_detractor = detractors[0] if detractors else None

    # Leader = highest positive contribution among sectors
    leading_sector = None
    if sectors:
        positive = [s for s in sectors if s["contribution_pct"] > 0]
        if positive:
            leading_sector = max(
                positive,
                key=lambda s: s["contribution_pct"],
            )

    # Laggard = most negative contribution among sectors
    lagging_sector = None
    if sectors:
        negative = [s for s in sectors if s["contribution_pct"] < 0]
        if negative:
            lagging_sector = min(
                negative,
                key=lambda s: s["contribution_pct"],
            )

    return {
        "portfolio_id": portfolio_id,
        "snapshot_id": movers["snapshot_id"],
        "return_pct": round(float(movers["return_pct"]), 2),
        "portfolio_value": round(float(movers["portfolio_value"]), 2),

        "top_contributor": _summarize(top_contributor),
        "top_detractor": _summarize(top_detractor),

        "all_contributors": [
            _summarize(h) for h in contributors
        ],
        "all_detractors": [
            _summarize(h) for h in detractors
        ],

        "leading_sector": _summarize_sector(leading_sector),
        "lagging_sector": _summarize_sector(lagging_sector),
        "all_sectors": [
            _summarize_sector(s) for s in sectors
        ],

        # Deterministic text — the LLM's fallback and reference
        "deterministic_explanation": (
            deterministic["explanation"] if deterministic else ""
        ),
    }


def _summarize(h: Optional[dict]) -> Optional[dict]:
    if h is None:
        return None

    return {
        "ticker": h["ticker"],
        "sector": h.get("sector") or "Unclassified",
        "pnl": round(float(h["pnl"]), 2),
        "return_pct": round(float(h["return_pct"]), 2),
        "contribution_pct": round(float(h["contribution_pct"]), 2),
        "weight_pct": round(float(h["weight_pct"]), 2),
    }


def _summarize_sector(s: Optional[dict]) -> Optional[dict]:
    if s is None:
        return None

    return {
        "sector": s["sector"],
        "holdings": list(s.get("holdings") or []),
        "contribution_pct": round(float(s["contribution_pct"]), 2),
        "return_pct": round(float(s["return_pct"]), 2),
        "weight_pct": round(float(s["weight_pct"]), 2),
    }


# =========================================================
# NUMBER EXTRACTION & VALIDATION
# =========================================================

# Matches: 3.71, +3.71, -3.71, 0.30, $17,475.00, $300, 1.78% etc.
# We strip percent signs and currency symbols and keep the numeric value.
_NUMBER_RE = re.compile(
    r"[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?|[-+]?\d+(?:\.\d+)?"
)


def extract_numbers(text: str) -> list:
    """
    Extract every numeric literal from a string.

    Returns a list of floats, normalized (commas removed).
    """
    if not text:
        return []

    matches = _NUMBER_RE.findall(text)
    out = []
    for m in matches:
        try:
            out.append(float(m.replace(",", "")))
        except ValueError:
            continue
    return out


def collect_fact_numbers(evidence: dict) -> set:
    """
    Build the set of numeric values we actually computed.

    These are the ONLY numbers the LLM is allowed to reference.
    """

    facts = set()

    # Rounding tolerance: we allow 2-decimal rounding, so both the
    # raw and the rounded values count as "known".
    def add(value):
        if value is None:
            return
        try:
            v = float(value)
        except (TypeError, ValueError):
            return
        facts.add(round(v, 2))
        # also add the absolute value so "subtracting 0.30" matches "-0.30"
        facts.add(round(abs(v), 2))
        # integer form (e.g. 300 vs 300.00)
        facts.add(float(int(v)) if v == int(v) else v)

    add(evidence.get("return_pct"))
    add(evidence.get("portfolio_value"))
    add(evidence.get("snapshot_id"))
    add(evidence.get("portfolio_id"))

    for key in ("top_contributor", "top_detractor"):
        h = evidence.get(key)
        if h:
            for field in ("pnl", "return_pct", "contribution_pct", "weight_pct"):
                add(h.get(field))

    for lst in ("all_contributors", "all_detractors"):
        for h in evidence.get(lst) or []:
            for field in ("pnl", "return_pct", "contribution_pct", "weight_pct"):
                add(h.get(field))

    for key in ("leading_sector", "lagging_sector"):
        s = evidence.get(key)
        if s:
            for field in ("contribution_pct", "return_pct", "weight_pct"):
                add(s.get(field))

    for s in evidence.get("all_sectors") or []:
        for field in ("contribution_pct", "return_pct", "weight_pct"):
            add(s.get(field))

    return facts


def validate_numbers(
    text: str,
    evidence: dict,
    tolerance: float = 0.05,
) -> dict:
    """
    Reject any number in `text` that isn't in our fact set
    (within `tolerance`).

    Returns:
        {
            "valid": bool,
            "unknown": [list of offending numbers]
        }
    """

    if not text:
        return {"valid": False, "unknown": []}

    facts = collect_fact_numbers(evidence)
    found = extract_numbers(text)

    # Small integers (0-20) and common ordinals are tolerated
    # because they're natural in prose ("top 3 holdings", "3 sentences").
    WHITELIST = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10}

    unknown = []

    for n in found:
        if n in WHITELIST:
            continue

        # Check if n matches any fact within tolerance
        matched = False
        for f in facts:
            if abs(abs(n) - abs(f)) <= tolerance:
                matched = True
                break

        if not matched:
            unknown.append(n)

    return {
        "valid": len(unknown) == 0,
        "unknown": unknown,
    }


# =========================================================
# FALLBACK
# =========================================================

def build_fallback(evidence: dict) -> dict:
    """
    Deterministic fallback used when:
      - the LLM call fails, or
      - the LLM output invents a number we didn't give it.
    """

    return {
        "explanation": evidence.get(
            "deterministic_explanation", ""
        ),
        "source": "deterministic_fallback",
        "validation": {
            "valid": True,
            "unknown": [],
        },
    }