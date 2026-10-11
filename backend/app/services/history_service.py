from sqlalchemy.orm import Session

from app.database.models import Snapshot


def get_snapshot_history(
    db: Session,
    portfolio_id: int,
):
    snapshots = (
        db.query(Snapshot)
        .filter(Snapshot.portfolio_id == portfolio_id)
        .order_by(Snapshot.created_at.asc(), Snapshot.id.asc())
        .all()
    )

    return [
        {
            "snapshot_id": s.id,
            "created_at": s.created_at.isoformat(),
            "portfolio_value": s.portfolio_value,
            "cost_basis": s.cost_basis,
            "pnl": s.pnl,
            "return_pct": s.return_pct,
        }
        for s in snapshots
    ]


def get_historical_summary(
    db: Session,
    portfolio_id: int,
):
    snapshots = (
        db.query(Snapshot)
        .filter(Snapshot.portfolio_id == portfolio_id)
        .order_by(Snapshot.created_at.asc(), Snapshot.id.asc())
        .all()
    )

    if not snapshots:
        return {
            "snapshot_count": 0,
            "current_value": 0,
            "first_value": 0,
            "total_return_pct": 0,
            "latest_snapshot_id": None,
        }

    first = snapshots[0]
    latest = snapshots[-1]

    return {
        "snapshot_count": len(snapshots),
        "current_value": round(latest.portfolio_value, 2),
        "first_value": round(first.portfolio_value, 2),
        "total_return_pct": round(latest.return_pct, 2),
        "latest_snapshot_id": latest.id,
    }