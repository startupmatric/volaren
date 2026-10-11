from sqlalchemy.orm import Session

from app.database.models import Holding, Portfolio, Snapshot


def get_or_create_portfolio(
    db: Session,
    name: str,
) -> Portfolio:
    portfolio = (
        db.query(Portfolio)
        .filter(Portfolio.name == name)
        .first()
    )

    if portfolio is None:
        portfolio = Portfolio(name=name)
        db.add(portfolio)
        db.flush()  # assigns portfolio.id without committing

    return portfolio


def save_snapshot(
    db: Session,
    portfolio_id: int,
    metrics: dict,
    df,
) -> Snapshot:
    snapshot = Snapshot(
        portfolio_id=portfolio_id,
        portfolio_value=metrics["portfolio_value"],
        cost_basis=metrics["cost_basis"],
        pnl=metrics["pnl"],
        return_pct=metrics["return_pct"],
    )

    db.add(snapshot)
    db.flush()  # assigns snapshot.id

    for _, row in df.iterrows():
        holding = Holding(
            snapshot_id=snapshot.id,
            ticker=str(row["ticker"]),
            shares=float(row["shares"]),
            avg_price=float(row["avg_price"]),
            current_price=float(row["current_price"]),
            sector=row.get("sector"),
            position_value=float(row["position_value"]),
            cost_basis=float(row["cost_basis"]),
            pnl=float(row["pnl"]),
            return_pct=float(row["return_pct"]),
            weight_pct=float(row["weight_pct"]),
            contribution_pct=float(row["contribution_pct"]),
        )
        db.add(holding)

    db.commit()
    db.refresh(snapshot)

    return snapshot


def list_portfolios(db: Session):
    return db.query(Portfolio).order_by(Portfolio.id).all()


def get_latest_snapshots(
    db: Session,
    portfolio_id: int,
    limit: int = 2,
):
    return (
        db.query(Snapshot)
        .filter(Snapshot.portfolio_id == portfolio_id)
        .order_by(Snapshot.created_at.desc(), Snapshot.id.desc())
        .limit(limit)
        .all()
    )
