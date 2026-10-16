"""
Volaren Portfolio Intelligence — MCP server.

Exposes the Volaren portfolio tools to any MCP client
(Claude Desktop, Cursor, custom agents) over stdio.

Tools exposed:
    - get_portfolio_summary
    - get_portfolio_movers
    - get_portfolio_sectors
    - get_portfolio_changes
    - get_portfolio_history

Design:
  - Every tool is a thin wrapper around an existing service function.
  - Business logic stays in backend/app/services/*.
  - The server runs standalone on the host and connects to Postgres
    at localhost:5433 (the Docker postgres port is forwarded there).

Run:
    python -m mcp_server.server

Or connect it from Claude Desktop via .mcp.json.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP


# =========================================================
# ENVIRONMENT
# =========================================================

# Load mcp_server/.env (if present) before importing anything that
# reads DATABASE_URL.
_ENV_PATH = Path(__file__).parent / ".env"
if _ENV_PATH.exists():
    load_dotenv(_ENV_PATH)

# Default to localhost:5433 if not set (matches the Docker-postgres
# port on the host after the 5432 → 5433 remap).
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+psycopg2://volaren:volaren@localhost:5433/volaren",
)


# =========================================================
# IMPORTS (after env is set)
# =========================================================

# These imports trigger app.* modules that read DATABASE_URL at import.
# Ensure `backend/` is on sys.path so `app.*` resolves.
_BACKEND_DIR = Path(__file__).parent.parent / "backend"
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from app.database.session import SessionLocal  # noqa: E402
from app.services.attribution_service import (  # noqa: E402
    get_movers,
    get_sector_attribution,
)
from app.services.diff_service import compute_diff  # noqa: E402
from app.services.history_service import get_snapshot_history  # noqa: E402
from app.services.persistence_service import get_latest_snapshots  # noqa: E402


# =========================================================
# MCP SERVER
# =========================================================

mcp = FastMCP("volaren-portfolio-intelligence")


# ---------------------------------------------------------
# TOOL: get_portfolio_summary
# ---------------------------------------------------------

@mcp.tool()
def get_portfolio_summary(portfolio_id: int) -> dict:
    """
    Return the latest snapshot summary for a portfolio.

    Use this to get the current portfolio value, cost basis,
    total P&L, and return percentage.
    """

    db = SessionLocal()
    try:
        snapshots = get_latest_snapshots(db, portfolio_id, limit=1)

        if not snapshots:
            raise ValueError(f"Portfolio {portfolio_id} has no snapshots")

        s = snapshots[0]

        return {
            "portfolio_id": portfolio_id,
            "snapshot_id": s.id,
            "portfolio_value": round(float(s.portfolio_value), 2),
            "cost_basis": round(float(s.cost_basis), 2),
            "pnl": round(float(s.pnl), 2),
            "return_pct": round(float(s.return_pct), 2),
        }
    finally:
        db.close()


# ---------------------------------------------------------
# TOOL: get_portfolio_movers
# ---------------------------------------------------------

@mcp.tool()
def get_portfolio_movers(portfolio_id: int) -> dict:
    """
    Return the biggest contributors and detractors for a portfolio's
    latest snapshot.

    Returns top contributors (positive impact) and top detractors
    (negative impact), each with contribution in percentage points.
    """

    db = SessionLocal()
    try:
        movers = get_movers(db, portfolio_id)

        if movers is None:
            raise ValueError(f"Portfolio {portfolio_id} has no snapshots")

        def _trim(rows):
            return [
                {
                    "ticker": r.get("ticker"),
                    "contribution_pct": round(float(r.get("contribution_pct", 0)), 2),
                    "return_pct": round(float(r.get("return_pct", 0)), 2),
                    "pnl": round(float(r.get("pnl", 0)), 2),
                    "weight_pct": round(float(r.get("weight_pct", 0)), 2),
                }
                for r in (rows or [])
            ]

        return {
            "portfolio_id": movers["portfolio_id"],
            "snapshot_id": movers["snapshot_id"],
            "portfolio_value": round(float(movers["portfolio_value"]), 2),
            "return_pct": round(float(movers["return_pct"]), 2),
            "top_contributors": _trim(movers.get("top_contributors")),
            "top_detractors": _trim(movers.get("top_detractors")),
        }
    finally:
        db.close()


# ---------------------------------------------------------
# TOOL: get_portfolio_sectors
# ---------------------------------------------------------

@mcp.tool()
def get_portfolio_sectors(portfolio_id: int) -> dict:
    """
    Return sector-level attribution for a portfolio's latest snapshot.

    Returns each sector's weight, return, and contribution in
    percentage points, plus the leading sector.
    """

    db = SessionLocal()
    try:
        attribution = get_sector_attribution(db, portfolio_id)

        if attribution is None:
            raise ValueError(f"Portfolio {portfolio_id} has no snapshots")

        sectors = attribution.get("sectors") or []

        positive = [s for s in sectors if s.get("contribution_pct", 0) > 0]
        leading = max(positive, key=lambda s: s["contribution_pct"]) if positive else None

        def _trim(s):
            return {
                "sector": s.get("sector"),
                "contribution_pct": round(float(s.get("contribution_pct", 0)), 2),
                "return_pct": round(float(s.get("return_pct", 0)), 2),
                "weight_pct": round(float(s.get("weight_pct", 0)), 2),
                "holdings": s.get("holdings") or [],
            }

        return {
            "portfolio_id": attribution["portfolio_id"],
            "snapshot_id": attribution["snapshot_id"],
            "portfolio_value": round(float(attribution["portfolio_value"]), 2),
            "return_pct": round(float(attribution["return_pct"]), 2),
            "leading_sector": _trim(leading) if leading else None,
            "sectors": [_trim(s) for s in sectors],
        }
    finally:
        db.close()


# ---------------------------------------------------------
# TOOL: get_portfolio_changes
# ---------------------------------------------------------

@mcp.tool()
def get_portfolio_changes(portfolio_id: int) -> dict:
    """
    Return what changed since the previous snapshot.

    Returns weight shifts, contribution shifts, new positions,
    and closed positions.
    """

    db = SessionLocal()
    try:
        diff = compute_diff(db, portfolio_id)

        if diff is None:
            raise ValueError(
                f"Portfolio {portfolio_id} needs at least 2 snapshots "
                f"to compute changes"
            )

        return diff
    finally:
        db.close()


# ---------------------------------------------------------
# TOOL: get_portfolio_history
# ---------------------------------------------------------

@mcp.tool()
def get_portfolio_history(portfolio_id: int) -> dict:
    """
    Return the full snapshot history for a portfolio.

    Use this to see how the portfolio evolved over time.
    """

    db = SessionLocal()
    try:
        history = get_snapshot_history(db, portfolio_id)

        if not history:
            raise ValueError(f"Portfolio {portfolio_id} has no snapshots")

        return {
            "portfolio_id": portfolio_id,
            "snapshots": history,
        }
    finally:
        db.close()


# =========================================================
# ENTRY POINT
# =========================================================

def main():
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()