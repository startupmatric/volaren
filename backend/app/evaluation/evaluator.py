"""
Evaluator — scores a single explanation against a golden case.

Uses validators.py for number/ticker extraction and comparison.
Pure function, no I/O, no LLM, easy to test.

Returns a full evaluation report:
  - grounding score (numbers grounded in evidence)
  - ticker accuracy score (no fake companies)
  - fact accuracy score (required facts covered)
  - unsupported numbers / tickers
  - missing expected facts
  - overall pass/fail
"""

import re

from app.evaluation.validators import (
    validate_numbers_grounded,
    validate_tickers_grounded,
)


# Pass thresholds
GROUNDING_THRESHOLD = 0.9
TICKER_THRESHOLD = 0.9
FACT_THRESHOLD = 0.8


# =========================================================
# PUBLIC API
# =========================================================

def evaluate_explanation(
    explanation: str,
    case: dict,
) -> dict:
    """
    Score a single explanation against a golden case.

    Args:
        explanation: the LLM-generated explanation text
        case:        a golden case dict (from datasets.py)
                     with keys 'name', 'evidence', 'expected'

    Returns:
        A dict with scores, unsupported claims, missing facts,
        and a pass/fail boolean.
    """

    case_name = case.get("name", "<unnamed>")
    evidence = case.get("evidence") or {}
    expected = case.get("expected") or {}

    if not explanation:
        return _empty_report(case_name, reason="empty_explanation")

    # ------------------------------------------------------
    # 1. Grounding — numbers must match evidence
    # ------------------------------------------------------

    number_check = validate_numbers_grounded(explanation, evidence)

    total_numbers = number_check["total_numbers"]
    if total_numbers == 0:
        grounding_score = 1.0
    else:
        matched = len(number_check["matched"])
        grounding_score = round(matched / total_numbers, 4)

    # ------------------------------------------------------
    # 2. Ticker accuracy — no fake companies
    # ------------------------------------------------------

    ticker_check = validate_tickers_grounded(explanation, evidence)

    total_tickers = len(ticker_check["found"]) + len(
        ticker_check["unsupported"]
    )
    if total_tickers == 0:
        ticker_score = 1.0
    else:
        ticker_score = round(
            len(ticker_check["found"]) / total_tickers,
            4,
        )

    # ------------------------------------------------------
    # 3. Fact accuracy — every expected fact is covered
    # ------------------------------------------------------

    fact_check = _check_expected_facts(explanation, expected)

    fact_score = fact_check["score"]

    # ------------------------------------------------------
    # Overall pass/fail
    # ------------------------------------------------------

    passed = (
        grounding_score >= GROUNDING_THRESHOLD
        and ticker_score >= TICKER_THRESHOLD
        and fact_score >= FACT_THRESHOLD
    )

    return {
        "case_name": case_name,
        "passed": passed,
        "scores": {
            "grounding": grounding_score,
            "ticker_accuracy": ticker_score,
            "fact_accuracy": fact_score,
        },
        "unsupported_numbers": number_check["unsupported"],
        "unsupported_tickers": ticker_check["unsupported"],
        "missing_expected_facts": fact_check["missing"],
        "found_expected_facts": fact_check["found"],
    }


# =========================================================
# FACT CHECKING
# =========================================================

def _check_expected_facts(
    explanation: str,
    expected: dict,
) -> dict:
    """
    Verify that every expected fact appears in the explanation.

    Facts can be:
      - numbers (matched with tolerance)
      - strings like "NVDA" or "Semiconductors" (substring match, case-insensitive)

    Special case: a numeric expected fact of 0.0 is skipped because
    the LLM will naturally describe a flat portfolio as "flat" rather
    than repeating the number zero.
    """

    if not expected:
        return {
            "score": 1.0,
            "found": {},
            "missing": {},
        }

    explanation_lower = explanation.lower()
    explanation_numbers = _extract_numbers_from_text(explanation)

    found = {}
    missing = {}

    for key, value in expected.items():
        if value is None:
            continue

        # Numeric expected fact
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            # Zero is implicit — the LLM may say "flat" without stating "0.00"
            if float(value) == 0.0:
                continue

            if _number_present(float(value), explanation_numbers):
                found[key] = value
            else:
                missing[key] = value
            continue

        # String expected fact
        value_str = str(value).lower().strip()
        if not value_str:
            continue

        if value_str in explanation_lower:
            found[key] = value
        else:
            missing[key] = value

    total = len(found) + len(missing)

    score = round(len(found) / total, 4) if total else 1.0

    return {
        "score": score,
        "found": found,
        "missing": missing,
    }


# =========================================================
# HELPERS
# =========================================================

_NUMBER_RE = re.compile(
    r"[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[-+]?\d+(?:\.\d+)?"
)


def _extract_numbers_from_text(text: str) -> list:
    """Extract all numbers from a string as floats."""
    out = []
    for m in _NUMBER_RE.findall(text or ""):
        try:
            out.append(float(m.replace(",", "")))
        except ValueError:
            continue
    return out


def _number_present(
    target: float,
    numbers: list,
    tolerance: float = 0.05,
) -> bool:
    """Check if a target number appears in the list, within tolerance."""
    for n in numbers:
        if abs(abs(n) - abs(target)) <= tolerance:
            return True
    return False


def _empty_report(case_name: str, reason: str = "unknown") -> dict:
    return {
        "case_name": case_name,
        "passed": False,
        "scores": {
            "grounding": 0.0,
            "ticker_accuracy": 0.0,
            "fact_accuracy": 0.0,
        },
        "unsupported_numbers": [],
        "unsupported_tickers": [],
        "missing_expected_facts": {},
        "found_expected_facts": {},
        "reason": reason,
    }
# =========================================================
# TOOL COVERAGE EVALUATION (Day 8a)
# =========================================================

def evaluate_tool_coverage(
    intent: str,
    tool_calls: list,
) -> dict:
    """
    Score whether the agent called the required tools for an intent.

    Args:
        intent:      e.g. "explain_movement"
        tool_calls:  list of dicts with at least a "name" key

    Returns:
        {
            "intent": str,
            "required": [tool names],
            "called": [tool names],
            "missing": [tool names],
            "satisfied": bool,
            "coverage": float (0..1),
        }
    """

    from app.agents.tool_registry import check_tool_coverage

    called_names = []

    for tc in tool_calls or []:
        if isinstance(tc, dict):
            name = tc.get("name")
        else:
            name = getattr(tc, "name", None)

        if name:
            called_names.append(name)

    return check_tool_coverage(intent, called_names)