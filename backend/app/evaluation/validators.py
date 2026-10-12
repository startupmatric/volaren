"""
Evaluation validators.

These functions take an LLM explanation and a structured evidence dict,
and check whether the explanation is grounded in the evidence.

Design principle: pure functions, no I/O, no LLM. Easy to test.

We extract three kinds of tokens from the explanation:

  1. Numbers     — "3.71", "$17,475.00", "-0.30" etc.
  2. Tickers     — uppercase tokens like NVDA, MSFT, GOOGL
  3. Percentages — numbers immediately followed by %

We then compare each against what the evidence says.
"""

import re
from typing import Any


# =========================================================
# EXTRACTION
# =========================================================

# Matches numbers with optional sign, optional commas, optional decimals
_NUMBER_RE = re.compile(
    r"[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[-+]?\d+(?:\.\d+)?"
)

# Matches tickers: 1-5 uppercase letters, optionally with . or - suffixes
# e.g. NVDA, MSFT, GOOGL, BRK.B, RDS-A
_TICKER_RE = re.compile(r"\b[A-Z]{2,5}(?:[.\-][A-Z]{1,3})?\b")

# Tickers that are common English words or known acronyms we want to skip
_TICKER_STOPWORDS = {
    "A", "I", "USA", "USD", "CEO", "CFO", "AI", "API", "UI", "UX",
    "IT", "OK", "NO", "UP", "DOWN", "THE", "AND", "FOR", "NOT",
    "ALL", "ANY", "BUY", "SELL", "LIVE", "BRIEF",
}


def extract_numbers(text: str) -> list:
    """Extract every numeric literal from text as floats."""
    if not text:
        return []

    out = []
    for m in _NUMBER_RE.findall(text):
        try:
            out.append(float(m.replace(",", "")))
        except ValueError:
            continue
    return out


def extract_tickers(text: str) -> list:
    """Extract every plausible stock ticker from text."""
    if not text:
        return []

    out = []
    for m in _TICKER_RE.findall(text):
        if m not in _TICKER_STOPWORDS:
            out.append(m)
    return out


# =========================================================
# EVIDENCE NUMBER SET
# =========================================================

def collect_evidence_numbers(evidence: dict) -> set:
    """
    Build the set of numeric facts the LLM is allowed to reference.

    We store both raw and absolute values, and integers when applicable.
    """
    facts = set()

    def add(value):
        if value is None:
            return
        try:
            v = float(value)
        except (TypeError, ValueError):
            return
        facts.add(round(v, 2))
        facts.add(round(abs(v), 2))
        if v == int(v):
            facts.add(float(int(v)))

    # Top-level
    for key in ("return_pct", "portfolio_value", "snapshot_id", "portfolio_id"):
        add(evidence.get(key))

    # Holdings (top and all)
    for key in ("top_contributor", "top_detractor"):
        h = evidence.get(key)
        if h:
            for field in ("pnl", "return_pct", "contribution_pct", "weight_pct", "shares", "avg_price", "current_price"):
                add(h.get(field))

    for lst in ("all_contributors", "all_detractors"):
        for h in evidence.get(lst) or []:
            for field in ("pnl", "return_pct", "contribution_pct", "weight_pct"):
                add(h.get(field))

    # Sectors
    for key in ("leading_sector", "lagging_sector"):
        s = evidence.get(key)
        if s:
            for field in ("contribution_pct", "return_pct", "weight_pct"):
                add(s.get(field))

    for s in evidence.get("all_sectors") or []:
        for field in ("contribution_pct", "return_pct", "weight_pct"):
            add(s.get(field))

    return facts


def collect_evidence_tickers(evidence: dict) -> set:
    """
    Build the set of tickers the LLM is allowed to reference.
    """
    tickers = set()

    for key in ("top_contributor", "top_detractor"):
        h = evidence.get(key)
        if h and h.get("ticker"):
            tickers.add(h["ticker"])

    for lst in ("all_contributors", "all_detractors"):
        for h in evidence.get(lst) or []:
            if h.get("ticker"):
                tickers.add(h["ticker"])

    for s in evidence.get("all_sectors") or []:
        for t in s.get("holdings") or []:
            tickers.add(t)

    for key in ("leading_sector", "lagging_sector"):
        s = evidence.get(key)
        if s:
            for t in s.get("holdings") or []:
                tickers.add(t)

    return tickers


# =========================================================
# VALIDATION
# =========================================================

def validate_numbers_grounded(
    explanation: str,
    evidence: dict,
    tolerance: float = 0.05,
) -> dict:
    """
    Check every number in `explanation` against the evidence.

    Returns:
        {
            "valid": bool,
            "total_numbers": int,
            "matched": [list of matched numbers],
            "unsupported": [list of numbers not found in evidence]
        }
    """
    if not explanation:
        return {
            "valid": False,
            "total_numbers": 0,
            "matched": [],
            "unsupported": [],
        }

    evidence_numbers = collect_evidence_numbers(evidence)
    extracted = extract_numbers(explanation)

    # Small integers 0-10 are allowed in prose ("top 3 holdings")
    WHITELIST = set(range(0, 11))

    matched = []
    unsupported = []

    for n in extracted:
        if n in WHITELIST:
            matched.append(n)
            continue

        found = False
        for e in evidence_numbers:
            if abs(abs(n) - abs(e)) <= tolerance:
                found = True
                break

        if found:
            matched.append(n)
        else:
            unsupported.append(n)

    return {
        "valid": len(unsupported) == 0,
        "total_numbers": len(extracted),
        "matched": matched,
        "unsupported": unsupported,
    }


def validate_tickers_grounded(
    explanation: str,
    evidence: dict,
) -> dict:
    """
    Check every ticker in `explanation` against the evidence.

    Returns:
        {
            "valid": bool,
            "found": [list of tickers found],
            "unsupported": [list of tickers not in evidence]
        }
    """
    if not explanation:
        return {
            "valid": False,
            "found": [],
            "unsupported": [],
        }

    allowed = collect_evidence_tickers(evidence)
    extracted = extract_tickers(explanation)

    found = []
    unsupported = []

    for t in extracted:
        if t in allowed:
            found.append(t)
        else:
            unsupported.append(t)

    return {
        "valid": len(unsupported) == 0,
        "found": found,
        "unsupported": unsupported,
    }