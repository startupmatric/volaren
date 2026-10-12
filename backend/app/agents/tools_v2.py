"""
Native LangGraph tools for the portfolio agent.

Each tool is a thin wrapper around an existing service function.
The services own the business logic; the tools only expose them
to the LLM in a safe, typed, callable form.

Design principles:
  - No business logic here — call the service.
  - Every tool returns a JSON-serializable dict.
  - Every tool accepts a single `portfolio_id` (multi-tenant ready).
  - Docstrings are precise — the LLM reads them to decide when to call.
"""

import time
from typing import Any, Optional

from langchain_core.tools import tool
from sqlalchemy.orm import Session

from app.services.attribution_service import (
    get_movers,
    get_sector_attribution,
)
from app.services.diff_service import compute_diff
from app.services.history_service import get_snapshot_history
from app.services.persistence_service import get_latest_snapshots


# =========================================================
# TOOL: get_portfolio_summary
# =========================================================

@tool
def get_portfolio_summary(portfolio_id: int) -> dict:
    """
    Return the latest snapshot summary for a portfolio.

    Use this when you need the current portfolio value, cost basis,
    total profit/loss, or the overall return percentage.

    Returns:
        {
            "portfolio_id": int,
            "snapshot_id": int,
            "portfolio_value": float,
            "cost_basis": float,
            "pnl": float,
            "return_pct": float,
        }

    Raises ValueError if the portfolio has no snapshots.
    """

    from app.database.session import SessionLocal

    db: Session = SessionLocal()
    try:
        snapshots = get_latest_snapshots(db, portfolio_id, limit=1)

        if not snapshots:
            raise ValueError(
                f"Portfolio {portfolio_id} has no snapshots"
            )

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


# =========================================================
# TOOL: get_portfolio_movers
# =========================================================

@tool
def get_portfolio_movers(portfolio_id: int) -> dict:
    """
    Return the biggest contributors and detractors for a portfolio's
    latest snapshot.

    Use this when you need to know WHICH holdings moved the portfolio
    and by how much. Returns top contributors (positive impact) and
    top detractors (negative impact), each with contribution in
    percentage points.

    Returns:
        {
            "portfolio_id": int,
            "snapshot_id": int,
            "portfolio_value": float,
            "return_pct": float,
            "top_contributors": [
                {"ticker": str, "contribution_pct": float, "return_pct": float, "pnl": float},
                ...
            ],
            "top_detractors": [ ... same shape ... ],
        }

    Raises ValueError if the portfolio has no snapshots.
    """

    from app.database.session import SessionLocal

    db: Session = SessionLocal()
    try:
        movers = get_movers(db, portfolio_id)

        if movers is None:
            raise ValueError(
                f"Portfolio {portfolio_id} has no snapshots"
            )

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


# =========================================================
# TOOL: get_portfolio_sectors
# =========================================================

@tool
def get_portfolio_sectors(portfolio_id: int) -> dict:
    """
    Return sector-level attribution for a portfolio's latest snapshot.

    Use this when you need to know which sectors drove the portfolio's
    performance, or which sector led the move. Returns each sector's
    weight, return, and contribution in percentage points, plus a
    convenience `leading_sector` field.

    Returns:
        {
            "portfolio_id": int,
            "snapshot_id": int,
            "portfolio_value": float,
            "return_pct": float,
            "leading_sector": {
                "sector": str,
                "contribution_pct": float,
                "return_pct": float,
                "weight_pct": float,
                "holdings": [str, ...],
            } or None,
            "sectors": [ ... same shape for each sector ... ],
        }

    Raises ValueError if the portfolio has no snapshots.
    """

    from app.database.session import SessionLocal

    db: Session = SessionLocal()
    try:
        attribution = get_sector_attribution(db, portfolio_id)

        if attribution is None:
            raise ValueError(
                f"Portfolio {portfolio_id} has no snapshots"
            )

        sectors = attribution.get("sectors") or []

        positive = [s for s in sectors if s.get("contribution_pct", 0) > 0]
        leading = None
        if positive:
            leading = max(positive, key=lambda s: s["contribution_pct"])

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


# =========================================================
# TOOL: get_portfolio_changes
# =========================================================

@tool
def get_portfolio_changes(portfolio_id: int) -> dict:
    """
    Return what changed since the previous snapshot.

    Use this when you need to know how weights shifted between
    snapshots, how individual contributions changed, or which
    positions were added or closed.

    Returns:
        {
            "portfolio_id": int,
            "previous_snapshot_id": int,
            "latest_snapshot_id": int,
            "portfolio_value_delta": float,
            "return_pct_delta": float,
            "weight_changes": [...],
            "contribution_changes": [...],
            "new_positions": [str, ...],
            "closed_positions": [str, ...],
        }

    Raises ValueError if the portfolio has fewer than 2 snapshots.
    """

    from app.database.session import SessionLocal

    db: Session = SessionLocal()
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


# =========================================================
# TOOL: get_portfolio_history
# =========================================================

@tool
def get_portfolio_history(portfolio_id: int) -> dict:
    """
    Return the full snapshot history for a portfolio.

    Use this when the user asks about the portfolio over time,
    wants to see the trajectory, or asks "how has my portfolio
    evolved?".

    Returns:
        {
            "portfolio_id": int,
            "snapshots": [
                {
                    "snapshot_id": int,
                    "created_at": str (ISO 8601),
                    "portfolio_value": float,
                    "return_pct": float,
                },
                ...
            ]
        }

    Raises ValueError if the portfolio has no snapshots.
    """

    from app.database.session import SessionLocal

    db: Session = SessionLocal()
    try:
        history = get_snapshot_history(db, portfolio_id)

        if not history:
            raise ValueError(
                f"Portfolio {portfolio_id} has no snapshots"
            )

        return {
            "portfolio_id": portfolio_id,
            "snapshots": history,
        }
    finally:
        db.close()


# =========================================================
# TOOL REGISTRY
# =========================================================

ALL_TOOLS = [
    get_portfolio_summary,
    get_portfolio_movers,
    get_portfolio_sectors,
    get_portfolio_changes,
    get_portfolio_history,
]


TOOLS_BY_NAME = {t.name: t for t in ALL_TOOLS}