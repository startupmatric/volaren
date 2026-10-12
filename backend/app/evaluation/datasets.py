"""
Golden evaluation datasets.

Each case is a self-contained scenario:
  - the evidence dict the LLM receives
  - the expected facts the LLM must respect

These cases are used by the evaluation harness (Step 4) to score
agent output for grounding, accuracy, and hallucination resistance.
"""


# =========================================================
# CASE 1 — typical gain
# =========================================================
#
# Reflects the shape of demo_portfolio_v2.csv:
#   NVDA, MSFT, AVGO gain; GOOGL drags slightly.
# Portfolio up +3.71% on $16,850 cost basis.

NVDA_LED_GAIN = {
    "name": "nvda_led_gain",
    "tags": ["positive", "typical"],
    "notes": "Portfolio up, one big gainer, one small drag.",

    "evidence": {
        "portfolio_id": 1,
        "snapshot_id": 12,
        "return_pct": 3.71,
        "portfolio_value": 17475.00,

        "top_contributor": {
            "ticker": "NVDA",
            "sector": "Semiconductors",
            "pnl": 300.0,
            "return_pct": 9.09,
            "contribution_pct": 1.78,
            "weight_pct": 20.60,
        },

        "top_detractor": {
            "ticker": "GOOGL",
            "sector": "Technology",
            "pnl": -50.0,
            "return_pct": -2.08,
            "contribution_pct": -0.30,
            "weight_pct": 13.45,
        },

        "all_contributors": [
            {
                "ticker": "NVDA",
                "sector": "Semiconductors",
                "pnl": 300.0,
                "return_pct": 9.09,
                "contribution_pct": 1.78,
                "weight_pct": 20.60,
            },
            {
                "ticker": "MSFT",
                "sector": "Technology",
                "pnl": 225.0,
                "return_pct": 2.94,
                "contribution_pct": 1.34,
                "weight_pct": 45.06,
            },
            {
                "ticker": "AVGO",
                "sector": "Semiconductors",
                "pnl": 150.0,
                "return_pct": 4.29,
                "contribution_pct": 0.89,
                "weight_pct": 20.89,
            },
        ],

        "all_detractors": [
            {
                "ticker": "GOOGL",
                "sector": "Technology",
                "pnl": -50.0,
                "return_pct": -2.08,
                "contribution_pct": -0.30,
                "weight_pct": 13.45,
            },
        ],

        "leading_sector": {
            "sector": "Semiconductors",
            "holdings": ["AVGO", "NVDA"],
            "contribution_pct": 2.67,
            "return_pct": 6.62,
            "weight_pct": 41.49,
        },

        "lagging_sector": None,

        "all_sectors": [
            {
                "sector": "Semiconductors",
                "holdings": ["AVGO", "NVDA"],
                "contribution_pct": 2.67,
                "return_pct": 6.62,
                "weight_pct": 41.49,
            },
            {
                "sector": "Technology",
                "holdings": ["GOOGL", "MSFT"],
                "contribution_pct": 1.04,
                "return_pct": 1.74,
                "weight_pct": 58.51,
            },
        ],

        "deterministic_explanation": (
            "Your portfolio is up +3.71%, currently worth $17,475.00. "
            "NVDA is the biggest contributor, adding +1.78pp to portfolio "
            "return. GOOGL is the biggest drag, subtracting 0.30pp from "
            "portfolio return. Semiconductors led performance at +2.67pp, "
            "driven by AVGO and NVDA."
        ),
    },

    "expected": {
        "portfolio_return": 3.71,
        "top_contributor": "NVDA",
        "top_detractor": "GOOGL",
        "leading_sector": "Semiconductors",
    },
}


# =========================================================
# CASE 2 — flat portfolio
# =========================================================
#
# Everything at zero. Tests that the agent doesn't invent movement.

FLAT_PORTFOLIO = {
    "name": "flat_portfolio",
    "tags": ["edge", "flat"],
    "notes": "Zero return, no contributors, no detractors.",

    "evidence": {
        "portfolio_id": 2,
        "snapshot_id": 1,
        "return_pct": 0.0,
        "portfolio_value": 10000.00,

        "top_contributor": None,
        "top_detractor": None,
        "all_contributors": [],
        "all_detractors": [],

        "leading_sector": None,
        "lagging_sector": None,
        "all_sectors": [],

        "deterministic_explanation": (
            "Your portfolio is flat at $10,000.00."
        ),
    },

    "expected": {
        "portfolio_return": 0.0,
    },
}


# =========================================================
# CASE 3 — negative portfolio
# =========================================================
#
# Both sides of the market. Tests that the agent doesn't
# describe a drag as a contributor and vice versa.

NEGATIVE_PORTFOLIO = {
    "name": "negative_portfolio",
    "tags": ["negative", "mixed"],
    "notes": "Portfolio down, but one holding still positive.",

    "evidence": {
        "portfolio_id": 3,
        "snapshot_id": 1,
        "return_pct": -2.50,
        "portfolio_value": 9750.00,

        "top_contributor": {
            "ticker": "MSFT",
            "sector": "Technology",
            "pnl": 100.0,
            "return_pct": 2.94,
            "contribution_pct": 0.60,
            "weight_pct": 30.00,
        },

        "top_detractor": {
            "ticker": "NVDA",
            "sector": "Semiconductors",
            "pnl": -250.0,
            "return_pct": -6.25,
            "contribution_pct": -3.10,
            "weight_pct": 40.00,
        },

        "all_contributors": [
            {
                "ticker": "MSFT",
                "sector": "Technology",
                "pnl": 100.0,
                "return_pct": 2.94,
                "contribution_pct": 0.60,
                "weight_pct": 30.00,
            },
        ],

        "all_detractors": [
            {
                "ticker": "NVDA",
                "sector": "Semiconductors",
                "pnl": -250.0,
                "return_pct": -6.25,
                "contribution_pct": -3.10,
                "weight_pct": 40.00,
            },
        ],

        "leading_sector": {
            "sector": "Technology",
            "holdings": ["MSFT"],
            "contribution_pct": 0.60,
            "return_pct": 2.94,
            "weight_pct": 30.00,
        },

        "lagging_sector": {
            "sector": "Semiconductors",
            "holdings": ["NVDA"],
            "contribution_pct": -3.10,
            "return_pct": -6.25,
            "weight_pct": 40.00,
        },

        "all_sectors": [
            {
                "sector": "Technology",
                "holdings": ["MSFT"],
                "contribution_pct": 0.60,
                "return_pct": 2.94,
                "weight_pct": 30.00,
            },
            {
                "sector": "Semiconductors",
                "holdings": ["NVDA"],
                "contribution_pct": -3.10,
                "return_pct": -6.25,
                "weight_pct": 40.00,
            },
        ],

        "deterministic_explanation": (
            "Your portfolio is down -2.50%, currently worth $9,750.00. "
            "MSFT is the biggest contributor, adding +0.60pp to portfolio "
            "return. NVDA is the biggest drag, subtracting 3.10pp from "
            "portfolio return. Technology led performance at +0.60pp, "
            "driven by MSFT. Semiconductors lagged at -3.10pp, held back "
            "by NVDA."
        ),
    },

    "expected": {
        "portfolio_return": -2.50,
        "top_contributor": "MSFT",
        "top_detractor": "NVDA",
        "leading_sector": "Technology",
        "lagging_sector": "Semiconductors",
    },
}


# =========================================================
# CASE 4 — single holding portfolio
# =========================================================
#
# Simplest possible. Tests that the agent doesn't invent
# a second position when there's only one.

SINGLE_HOLDING = {
    "name": "single_holding",
    "tags": ["edge", "minimal"],
    "notes": "One position only.",

    "evidence": {
        "portfolio_id": 4,
        "snapshot_id": 1,
        "return_pct": 9.09,
        "portfolio_value": 3600.00,

        "top_contributor": {
            "ticker": "NVDA",
            "sector": "Semiconductors",
            "pnl": 300.0,
            "return_pct": 9.09,
            "contribution_pct": 9.09,
            "weight_pct": 100.00,
        },

        "top_detractor": None,

        "all_contributors": [
            {
                "ticker": "NVDA",
                "sector": "Semiconductors",
                "pnl": 300.0,
                "return_pct": 9.09,
                "contribution_pct": 9.09,
                "weight_pct": 100.00,
            },
        ],

        "all_detractors": [],

        "leading_sector": {
            "sector": "Semiconductors",
            "holdings": ["NVDA"],
            "contribution_pct": 9.09,
            "return_pct": 9.09,
            "weight_pct": 100.00,
        },

        "lagging_sector": None,

        "all_sectors": [
            {
                "sector": "Semiconductors",
                "holdings": ["NVDA"],
                "contribution_pct": 9.09,
                "return_pct": 9.09,
                "weight_pct": 100.00,
            },
        ],

        "deterministic_explanation": (
            "Your portfolio is up +9.09%, currently worth $3,600.00. "
            "NVDA is the biggest contributor, adding +9.09pp to portfolio "
            "return. Semiconductors led performance at +9.09pp, driven by "
            "NVDA."
        ),
    },

    "expected": {
        "portfolio_return": 9.09,
        "top_contributor": "NVDA",
        "leading_sector": "Semiconductors",
    },
}


# =========================================================
# CASE 5 — unclassified sector
# =========================================================
#
# Tests that the agent handles a missing sector gracefully.

UNCLASSIFIED_SECTOR = {
    "name": "unclassified_sector",
    "tags": ["edge"],
    "notes": "Holdings without a sector label.",

    "evidence": {
        "portfolio_id": 5,
        "snapshot_id": 1,
        "return_pct": 2.00,
        "portfolio_value": 10200.00,

        "top_contributor": {
            "ticker": "ACME",
            "sector": "Unclassified",
            "pnl": 200.0,
            "return_pct": 10.00,
            "contribution_pct": 2.00,
            "weight_pct": 100.00,
        },

        "top_detractor": None,

        "all_contributors": [
            {
                "ticker": "ACME",
                "sector": "Unclassified",
                "pnl": 200.0,
                "return_pct": 10.00,
                "contribution_pct": 2.00,
                "weight_pct": 100.00,
            },
        ],

        "all_detractors": [],

        "leading_sector": {
            "sector": "Unclassified",
            "holdings": ["ACME"],
            "contribution_pct": 2.00,
            "return_pct": 10.00,
            "weight_pct": 100.00,
        },

        "lagging_sector": None,

        "all_sectors": [
            {
                "sector": "Unclassified",
                "holdings": ["ACME"],
                "contribution_pct": 2.00,
                "return_pct": 10.00,
                "weight_pct": 100.00,
            },
        ],

        "deterministic_explanation": (
            "Your portfolio is up +2.00%, currently worth $10,200.00. "
            "ACME is the biggest contributor, adding +2.00pp to portfolio "
            "return. Unclassified led performance at +2.00pp, driven by "
            "ACME."
        ),
    },

    "expected": {
        "portfolio_return": 2.00,
        "top_contributor": "ACME",
        "leading_sector": "Unclassified",
    },
}


# =========================================================
# DATASET REGISTRY
# =========================================================

GOLDEN_CASES = [
    NVDA_LED_GAIN,
    FLAT_PORTFOLIO,
    NEGATIVE_PORTFOLIO,
    SINGLE_HOLDING,
    UNCLASSIFIED_SECTOR,
]


def get_case_by_name(name: str):
    """Return a golden case dict by its `name`, or None."""
    for case in GOLDEN_CASES:
        if case["name"] == name:
            return case
    return None


def get_cases_by_tag(tag: str):
    """Return all golden cases with the given tag."""
    return [c for c in GOLDEN_CASES if tag in c.get("tags", [])]