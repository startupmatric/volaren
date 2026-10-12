"""
Tests for the @tool-decorated functions in tools_v2.py.

The tools import service functions at module load time, so we
patch the imported names at the tools_v2 module level.

We also patch SessionLocal so tools don't try to open a real DB.
"""

from unittest.mock import MagicMock, patch

import pytest


# =========================================================
# Tool registry / metadata
# =========================================================

def test_all_tools_registered():
    from app.agents.tools_v2 import ALL_TOOLS, TOOLS_BY_NAME

    names = [t.name for t in ALL_TOOLS]

    assert "get_portfolio_summary" in names
    assert "get_portfolio_movers" in names
    assert "get_portfolio_sectors" in names
    assert "get_portfolio_changes" in names
    assert "get_portfolio_history" in names

    assert TOOLS_BY_NAME["get_portfolio_movers"].name == "get_portfolio_movers"


def test_tools_have_docstrings():
    from app.agents.tools_v2 import ALL_TOOLS

    for t in ALL_TOOLS:
        assert t.description, f"{t.name} has no description"
        assert len(t.description) > 50, f"{t.name} description too short"


def test_tools_accept_portfolio_id():
    from app.agents.tools_v2 import ALL_TOOLS

    for t in ALL_TOOLS:
        schema = t.args_schema.model_json_schema()
        props = schema.get("properties", {})
        assert "portfolio_id" in props, f"{t.name} missing portfolio_id arg"


# =========================================================
# Helpers
# =========================================================

def _patch_session_local():
    """Patch SessionLocal as the tools import it (locally)."""
    return patch(
        "app.database.session.SessionLocal",
        return_value=MagicMock(),
    )


def _fake_snapshot():
    snap = MagicMock()
    snap.id = 14
    snap.portfolio_value = 17475.0
    snap.cost_basis = 16850.0
    snap.pnl = 625.0
    snap.return_pct = 3.71
    return snap


# =========================================================
# Tool invocation (patched at module level)
# =========================================================

def test_get_portfolio_summary_returns_expected_shape():
    from app.agents import tools_v2

    with patch.object(
        tools_v2,
        "get_latest_snapshots",
        return_value=[_fake_snapshot()],
    ), _patch_session_local():
        result = tools_v2.get_portfolio_summary.invoke({"portfolio_id": 1})

    assert result["portfolio_id"] == 1
    assert result["snapshot_id"] == 14
    assert result["portfolio_value"] == 17475.0
    assert result["cost_basis"] == 16850.0
    assert result["pnl"] == 625.0
    assert result["return_pct"] == 3.71


def test_get_portfolio_summary_raises_for_no_snapshots():
    from app.agents import tools_v2

    with patch.object(
        tools_v2,
        "get_latest_snapshots",
        return_value=[],
    ), _patch_session_local():
        with pytest.raises(ValueError, match="no snapshots"):
            tools_v2.get_portfolio_summary.invoke({"portfolio_id": 999})


def test_get_portfolio_movers_returns_expected_shape():
    from app.agents import tools_v2

    fake_movers = {
        "portfolio_id": 1,
        "snapshot_id": 14,
        "portfolio_value": 17475.0,
        "return_pct": 3.71,
        "top_contributors": [
            {
                "ticker": "NVDA",
                "contribution_pct": 1.78,
                "return_pct": 9.09,
                "pnl": 300.0,
                "weight_pct": 20.60,
            },
        ],
        "top_detractors": [
            {
                "ticker": "GOOGL",
                "contribution_pct": -0.30,
                "return_pct": -2.08,
                "pnl": -50.0,
                "weight_pct": 13.45,
            },
        ],
    }

    with patch.object(
        tools_v2,
        "get_movers",
        return_value=fake_movers,
    ), _patch_session_local():
        result = tools_v2.get_portfolio_movers.invoke({"portfolio_id": 1})

    assert result["portfolio_id"] == 1
    assert len(result["top_contributors"]) == 1
    assert result["top_contributors"][0]["ticker"] == "NVDA"
    assert result["top_contributors"][0]["contribution_pct"] == 1.78
    assert len(result["top_detractors"]) == 1
    assert result["top_detractors"][0]["ticker"] == "GOOGL"


def test_get_portfolio_sectors_returns_leading_sector():
    from app.agents import tools_v2

    fake_attribution = {
        "portfolio_id": 1,
        "snapshot_id": 14,
        "portfolio_value": 17475.0,
        "return_pct": 3.71,
        "sectors": [
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
    }

    with patch.object(
        tools_v2,
        "get_sector_attribution",
        return_value=fake_attribution,
    ), _patch_session_local():
        result = tools_v2.get_portfolio_sectors.invoke({"portfolio_id": 1})

    assert result["portfolio_id"] == 1
    assert result["leading_sector"] is not None
    assert result["leading_sector"]["sector"] == "Semiconductors"
    assert result["leading_sector"]["contribution_pct"] == 2.67
    assert len(result["sectors"]) == 2


def test_get_portfolio_changes_raises_for_no_diff():
    from app.agents import tools_v2

    with patch.object(
        tools_v2,
        "compute_diff",
        return_value=None,
    ), _patch_session_local():
        with pytest.raises(ValueError, match="at least 2 snapshots"):
            tools_v2.get_portfolio_changes.invoke({"portfolio_id": 1})


def test_get_portfolio_history_returns_snapshots():
    from app.agents import tools_v2

    fake_history = [
        {
            "snapshot_id": 1,
            "created_at": "2026-10-12T00:00:00",
            "portfolio_value": 16850.0,
            "return_pct": 0.0,
        },
        {
            "snapshot_id": 2,
            "created_at": "2026-10-12T01:00:00",
            "portfolio_value": 17475.0,
            "return_pct": 3.71,
        },
    ]

    with patch.object(
        tools_v2,
        "get_snapshot_history",
        return_value=fake_history,
    ), _patch_session_local():
        result = tools_v2.get_portfolio_history.invoke({"portfolio_id": 1})

    assert result["portfolio_id"] == 1
    assert len(result["snapshots"]) == 2
    assert result["snapshots"][0]["portfolio_value"] == 16850.0