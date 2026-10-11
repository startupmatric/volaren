from typing import Optional

from sqlalchemy.orm import Session

from app.database.models import Holding, Snapshot
from app.services.persistence_service import get_latest_snapshots


def _holdings_by_ticker(snapshot: Snapshot) -> dict:
    return {h.ticker: h for h in snapshot.holdings}


def compute_diff(
    db: Session,
    portfolio_id: int,
) -> Optional[dict]:
    """
    Compare the two most recent snapshots for a portfolio.

    Returns None if there are fewer than 2 snapshots.
    """

    snapshots = get_latest_snapshots(db, portfolio_id, limit=2)

    if len(snapshots) < 2:
        return None

    latest = snapshots[0]
    previous = snapshots[1]

    latest_holdings = _holdings_by_ticker(latest)
    previous_holdings = _holdings_by_ticker(previous)

    all_tickers = sorted(
        set(latest_holdings.keys()) | set(previous_holdings.keys())
    )

    weight_changes = []
    contribution_changes = []

    for ticker in all_tickers:
        in_latest = ticker in latest_holdings
        in_previous = ticker in previous_holdings

        if in_latest and in_previous:
            h_latest = latest_holdings[ticker]
            h_prev = previous_holdings[ticker]

            weight_changes.append({
                "ticker": ticker,
                "weight_before_pct": round(h_prev.weight_pct, 4),
                "weight_after_pct": round(h_latest.weight_pct, 4),
                "weight_delta_pct": round(
                    h_latest.weight_pct - h_prev.weight_pct, 4
                ),
            })

            contribution_changes.append({
                "ticker": ticker,
                "contribution_before_pct": round(h_prev.contribution_pct, 4),
                "contribution_after_pct": round(h_latest.contribution_pct, 4),
                "contribution_delta_pct": round(
                    h_latest.contribution_pct - h_prev.contribution_pct, 4
                ),
            })

    new_positions = sorted(
        set(latest_holdings.keys()) - set(previous_holdings.keys())
    )
    closed_positions = sorted(
        set(previous_holdings.keys()) - set(latest_holdings.keys())
    )

    weight_changes.sort(
        key=lambda x: abs(x["weight_delta_pct"]),
        reverse=True,
    )
    contribution_changes.sort(
        key=lambda x: abs(x["contribution_delta_pct"]),
        reverse=True,
    )

    return {
        "portfolio_id": portfolio_id,
        "previous_snapshot_id": previous.id,
        "latest_snapshot_id": latest.id,
        "previous_created_at": previous.created_at,
        "latest_created_at": latest.created_at,
        "portfolio_value_before": previous.portfolio_value,
        "portfolio_value_after": latest.portfolio_value,
        "portfolio_value_delta": round(
            latest.portfolio_value - previous.portfolio_value, 4
        ),
        "return_pct_before": previous.return_pct,
        "return_pct_after": latest.return_pct,
        "return_pct_delta": round(
            latest.return_pct - previous.return_pct, 4
        ),
        "weight_changes": weight_changes,
        "contribution_changes": contribution_changes,
        "new_positions": new_positions,
        "closed_positions": closed_positions,
    }