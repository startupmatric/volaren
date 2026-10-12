from typing import Optional

from sqlalchemy.orm import Session

from app.database.models import Holding, Snapshot


def _latest_snapshot(
    db: Session,
    portfolio_id: int,
) -> Optional[Snapshot]:
    return (
        db.query(Snapshot)
        .filter(Snapshot.portfolio_id == portfolio_id)
        .order_by(Snapshot.created_at.desc(), Snapshot.id.desc())
        .first()
    )


def _holding_to_dict(h: Holding) -> dict:
    return {
        "ticker": h.ticker,
        "sector": h.sector or "Unclassified",
        "shares": h.shares,
        "avg_price": h.avg_price,
        "current_price": h.current_price,
        "position_value": h.position_value,
        "cost_basis": h.cost_basis,
        "pnl": h.pnl,
        "return_pct": h.return_pct,
        "weight_pct": h.weight_pct,
        "contribution_pct": h.contribution_pct,
    }


def get_movers(
    db: Session,
    portfolio_id: int,
    limit: int = 5,
) -> Optional[dict]:
    """
    Top gainers, top losers, top contributors, top detractors
    from the latest snapshot for the given portfolio.

    Returns None if no snapshots exist.
    """

    snapshot = _latest_snapshot(db, portfolio_id)

    if snapshot is None:
        return None

    holdings = [_holding_to_dict(h) for h in snapshot.holdings]

    if not holdings:
        return {
            "portfolio_id": portfolio_id,
            "snapshot_id": snapshot.id,
            "snapshot_created_at": snapshot.created_at.isoformat(),
            "portfolio_value": snapshot.portfolio_value,
            "return_pct": snapshot.return_pct,
            "top_gainers": [],
            "top_losers": [],
            "top_contributors": [],
            "top_detractors": [],
        }

    by_pnl_desc = sorted(
        holdings,
        key=lambda h: h["pnl"],
        reverse=True,
    )
    by_contribution_desc = sorted(
        holdings,
        key=lambda h: h["contribution_pct"],
        reverse=True,
    )

    # Gainers: strictly positive PnL, descending
    top_gainers = [
        h for h in by_pnl_desc if h["pnl"] > 0
    ][:limit]

    # Losers: strictly negative PnL, ascending (worst first)
    top_losers = [
        h for h in sorted(holdings, key=lambda x: x["pnl"])
        if h["pnl"] < 0
    ][:limit]

    # Contributors: strictly positive contribution
    top_contributors = [
        h for h in by_contribution_desc
        if h["contribution_pct"] > 0
    ][:limit]

    # Detractors: strictly negative contribution
    top_detractors = [
        h for h in sorted(
            holdings,
            key=lambda x: x["contribution_pct"],
        )
        if h["contribution_pct"] < 0
    ][:limit]

    return {
        "portfolio_id": portfolio_id,
        "snapshot_id": snapshot.id,
        "snapshot_created_at": snapshot.created_at.isoformat(),
        "portfolio_value": snapshot.portfolio_value,
        "return_pct": snapshot.return_pct,
        "top_gainers": top_gainers,
        "top_losers": top_losers,
        "top_contributors": top_contributors,
        "top_detractors": top_detractors,
    }


def get_sector_attribution(
    db: Session,
    portfolio_id: int,
) -> Optional[dict]:
    """
    Aggregate holdings by sector for the latest snapshot.

    Returns None if no snapshots exist.
    """

    snapshot = _latest_snapshot(db, portfolio_id)

    if snapshot is None:
        return None

    holdings = [_holding_to_dict(h) for h in snapshot.holdings]

    if not holdings:
        return {
            "portfolio_id": portfolio_id,
            "snapshot_id": snapshot.id,
            "snapshot_created_at": snapshot.created_at.isoformat(),
            "portfolio_value": snapshot.portfolio_value,
            "return_pct": snapshot.return_pct,
            "sectors": [],
        }

    total_value = sum(h["position_value"] for h in holdings)
    total_cost = sum(h["cost_basis"] for h in holdings)

    # Aggregate
    buckets: dict = {}

    for h in holdings:
        sector = h["sector"]
        if sector not in buckets:
            buckets[sector] = {
                "sector": sector,
                "position_value": 0.0,
                "cost_basis": 0.0,
                "pnl": 0.0,
                "holdings": [],
            }
        buckets[sector]["position_value"] += h["position_value"]
        buckets[sector]["cost_basis"] += h["cost_basis"]
        buckets[sector]["pnl"] += h["pnl"]
        buckets[sector]["holdings"].append(h["ticker"])

    sectors = []

    for sector, data in buckets.items():
        value = data["position_value"]
        cost = data["cost_basis"]
        pnl = data["pnl"]

        weight_pct = (
            (value / total_value) * 100 if total_value else 0.0
        )
        return_pct = (
            (pnl / cost) * 100 if cost else 0.0
        )
        contribution_pct = (
            (pnl / total_cost) * 100 if total_cost else 0.0
        )

        sectors.append({
            "sector": sector,
            "holdings": sorted(data["holdings"]),
            "position_value": round(value, 2),
            "cost_basis": round(cost, 2),
            "pnl": round(pnl, 2),
            "weight_pct": round(weight_pct, 4),
            "return_pct": round(return_pct, 4),
            "contribution_pct": round(contribution_pct, 4),
        })

    # Sort by absolute contribution, largest first
    sectors.sort(
        key=lambda s: abs(s["contribution_pct"]),
        reverse=True,
    )

    return {
        "portfolio_id": portfolio_id,
        "snapshot_id": snapshot.id,
        "snapshot_created_at": snapshot.created_at.isoformat(),
        "portfolio_value": snapshot.portfolio_value,
        "return_pct": snapshot.return_pct,
        "sectors": sectors,
    }