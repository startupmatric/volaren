"""
Tool registry — declares which tools each intent requires.

This is separate from tools_v2.py because:
  - tools_v2 defines the *capabilities* the agent has
  - tool_registry declares the *policy* of what's expected per intent

The evaluator uses this to check: did the agent call the right tools
for the question it was asked?
"""

from typing import Dict, List, Optional


# =========================================================
# INTENTS
# =========================================================

INTENT_EXPLAIN_MOVEMENT = "explain_movement"
INTENT_PORTFOLIO_SUMMARY = "portfolio_summary"
INTENT_PORTFOLIO_HISTORY = "portfolio_history"
INTENT_PORTFOLIO_CHANGES = "portfolio_changes"

ALL_INTENTS = [
    INTENT_EXPLAIN_MOVEMENT,
    INTENT_PORTFOLIO_SUMMARY,
    INTENT_PORTFOLIO_HISTORY,
    INTENT_PORTFOLIO_CHANGES,
]


# =========================================================
# INTENT → REQUIRED TOOLS
# =========================================================
#
# Each intent declares:
#   - required: every tool in this list MUST be called
#   - optional: tools that MAY be called (not required, not penalized)
#
# The evaluator checks that all `required` tools were called.
# Calling extra optional tools is fine.

INTENT_REQUIREMENTS: Dict[str, Dict[str, List[str]]] = {

    INTENT_EXPLAIN_MOVEMENT: {
        "required": [
            "get_portfolio_movers",
            "get_portfolio_summary",
            "get_portfolio_sectors",
        ],
        "optional": [
            "get_portfolio_changes",
        ],
    },

    INTENT_PORTFOLIO_SUMMARY: {
        "required": [
            "get_portfolio_summary",
        ],
        "optional": [],
    },

    INTENT_PORTFOLIO_HISTORY: {
        "required": [
            "get_portfolio_history",
        ],
        "optional": [],
    },

    INTENT_PORTFOLIO_CHANGES: {
        "required": [
            "get_portfolio_changes",
        ],
        "optional": [],
    },
}


# =========================================================
# HELPERS
# =========================================================

def get_required_tools(intent: str) -> List[str]:
    """Return the required tool names for an intent."""
    spec = INTENT_REQUIREMENTS.get(intent)
    if spec is None:
        return []
    return list(spec.get("required", []))


def get_optional_tools(intent: str) -> List[str]:
    """Return the optional tool names for an intent."""
    spec = INTENT_REQUIREMENTS.get(intent)
    if spec is None:
        return []
    return list(spec.get("optional", []))


def is_valid_intent(intent: str) -> bool:
    """Check whether an intent string is recognized."""
    return intent in INTENT_REQUIREMENTS


def check_tool_coverage(
    intent: str,
    called_tools: List[str],
) -> dict:
    """
    Check whether the required tools were called for an intent.

    Args:
        intent:        the intent string (e.g. "explain_movement")
        called_tools:  list of tool names the agent actually called

    Returns:
        {
            "intent": str,
            "required": [list of required tool names],
            "called": [list of tools the agent called],
            "missing": [required tools NOT called],
            "satisfied": bool,
            "coverage": float (0..1),
        }
    """

    required = get_required_tools(intent)
    called_set = set(called_tools)

    missing = [t for t in required if t not in called_set]

    total = len(required)
    matched = total - len(missing)
    coverage = round(matched / total, 4) if total else 1.0

    return {
        "intent": intent,
        "required": required,
        "called": sorted(called_set),
        "missing": missing,
        "satisfied": len(missing) == 0,
        "coverage": coverage,
    }