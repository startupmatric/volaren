"""
Tests for the MCP server.

We mock the underlying service functions so tests don't hit the DB
and don't need a running Postgres.
"""

from unittest.mock import MagicMock, patch

import pytest


# =========================================================
# Tool registry / metadata
# =========================================================

def test_mcp_server_has_all_tools():
    from mcp_server.server import mcp

    tools = mcp._tool_manager._tools
    names = sorted(tools.keys())

    assert names == [
        "get_portfolio_changes",
        "get_portfolio_history",
        "get_portfolio_movers",
        "get_portfolio_sectors",
        "get_portfolio_summary",
    ]


def test_tools_have_descriptions():
    from mcp_server.server import mcp

    tools = mcp._tool_manager._tools

    for name, tool in tools.items():
        assert tool.description, f"{name} has no description"
        assert len(tool.description) > 30


# =========================================================
# Fixtures
# =========================================================

@pytest.fixture
def patch_session():
    """Patch SessionLocal to return a mock session."""
    with patch("mcp_server.server.SessionLocal", return_value=MagicMock()):
        yield


# =========================================================
# get_portfolio_summary
# =========================================================

def test_summary_returns_expected_shape(patch_session):
    from mcp_server.server import get_portfolio_summary

    fake = MagicMock()
    fake.id = 14
    fake.portfolio_value = 17475.0
    fake.cost_basis = 16850.0
    fake.pnl = 625.0
    fake.return_pct = 3.71

    with patch(
        "mcp_server.server.get_latest_snapshots",
        return_value=[fake],
    ):
        result = get_portfolio_summary(portfolio_id=1)

    assert result["portfolio_id"] == 1
    assert result["snapshot_id"] == 14
    assert result["portfolio_value"] == 17475.0
    assert result["return_pct"] == 3.71


def test_summary_raises_for_empty_portfolio(patch_session):
    from mcp_server.server import get_portfolio_summary

    with patch(
        "mcp_server.server.get_latest_snapshots",
        return_value=[],
    ):
        with pytest.raises(ValueError, match="no snapshots"):
            get_portfolio_summary(portfolio_id=999)


# =========================================================
# get_portfolio_movers
# =========================================================

def test_movers_returns_contributors(patch_session):
    from mcp_server.server import get_portfolio_movers

    fake = {
        "portfolio_id": 1,
        "snapshot_id": 14,
        "portfolio_value": 17475.0,
        "return_pct": 3.71,
        "top_contributors": [
            {"ticker": "NVDA", "contribution_pct": 1.78, "return_pct": 9.09, "pnl": 300.0, "weight_pct": 20.6},
        ],
        "top_detractors": [
            {"ticker": "GOOGL", "contribution_pct": -0.30, "return_pct": -2.08, "pnl": -50.0, "weight_pct": 13.45},
        ],
    }

    with patch("mcp_server.server.get_movers", return_value=fake):
        result = get_portfolio_movers(portfolio_id=1)

    assert result["top_contributors"][0]["ticker"] == "NVDA"
    assert result["top_detractors"][0]["ticker"] == "GOOGL"


# =========================================================
# get_portfolio_sectors
# =========================================================

def test_sectors_finds_leading(patch_session):
    from mcp_server.server import get_portfolio_sectors

    fake = {
        "portfolio_id": 1,
        "snapshot_id": 14,
        "portfolio_value": 17475.0,
        "return_pct": 3.71,
        "sectors": [
            {"sector": "Semiconductors", "holdings": ["NVDA"], "contribution_pct": 2.67, "return_pct": 6.62, "weight_pct": 41.49},
            {"sector": "Technology", "holdings": ["MSFT"], "contribution_pct": 1.04, "return_pct": 1.74, "weight_pct": 58.51},
        ],
    }

    with patch("mcp_server.server.get_sector_attribution", return_value=fake):
        result = get_portfolio_sectors(portfolio_id=1)

    assert result["leading_sector"]["sector"] == "Semiconductors"


# =========================================================
# get_portfolio_history
# =========================================================

def test_history_returns_snapshots(patch_session):
    from mcp_server.server import get_portfolio_history

    fake = [
        {"snapshot_id": 1, "created_at": "2026-10-16T00:00:00", "portfolio_value": 17475.0, "return_pct": 3.71},
        {"snapshot_id": 2, "created_at": "2026-10-16T01:00:00", "portfolio_value": 17475.0, "return_pct": 3.71},
    ]

    with patch("mcp_server.server.get_snapshot_history", return_value=fake):
        result = get_portfolio_history(portfolio_id=1)

    assert len(result["snapshots"]) == 2


# =========================================================
# get_portfolio_changes
# =========================================================

def test_changes_raises_for_single_snapshot(patch_session):
    from mcp_server.server import get_portfolio_changes

    with patch("mcp_server.server.compute_diff", return_value=None):
        with pytest.raises(ValueError, match="at least 2 snapshots"):
            get_portfolio_changes(portfolio_id=1)