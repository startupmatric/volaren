import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, Portfolio, Snapshot
from app.services.history_service import (
    get_historical_summary,
    get_snapshot_history,
)


@pytest.fixture
def db_session():
    """In-memory SQLite for isolated history tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()


def _add_snapshot(
    db,
    portfolio_id,
    portfolio_value,
    cost_basis,
    return_pct,
):
    pnl = portfolio_value - cost_basis
    snap = Snapshot(
        portfolio_id=portfolio_id,
        portfolio_value=portfolio_value,
        cost_basis=cost_basis,
        pnl=pnl,
        return_pct=return_pct,
    )
    db.add(snap)
    db.flush()
    return snap


def test_history_empty_portfolio(db_session):
    portfolio = Portfolio(name="Empty")
    db_session.add(portfolio)
    db_session.flush()

    history = get_snapshot_history(db_session, portfolio.id)
    summary = get_historical_summary(db_session, portfolio.id)

    assert history == []
    assert summary["snapshot_count"] == 0
    assert summary["current_value"] == 0
    assert summary["total_return_pct"] == 0
    assert summary["latest_snapshot_id"] is None


def test_history_returns_snapshots_in_chronological_order(db_session):
    portfolio = Portfolio(name="Test")
    db_session.add(portfolio)
    db_session.flush()

    # Insert out of order to prove ordering is by created_at, not id
    _add_snapshot(db_session, portfolio.id, 17000, 16850, 0.89)
    _add_snapshot(db_session, portfolio.id, 18000, 16850, 6.82)
    _add_snapshot(db_session, portfolio.id, 17500, 16850, 3.86)

    db_session.commit()

    history = get_snapshot_history(db_session, portfolio.id)

    assert len(history) == 3
    assert history[0]["portfolio_value"] == 17000
    assert history[1]["portfolio_value"] == 18000
    assert history[2]["portfolio_value"] == 17500


def test_history_snapshot_fields(db_session):
    portfolio = Portfolio(name="Test")
    db_session.add(portfolio)
    db_session.flush()

    _add_snapshot(db_session, portfolio.id, 17500, 16850, 3.86)
    db_session.commit()

    history = get_snapshot_history(db_session, portfolio.id)
    entry = history[0]

    assert "snapshot_id" in entry
    assert "created_at" in entry
    assert entry["portfolio_value"] == 17500
    assert entry["cost_basis"] == 16850
    assert entry["pnl"] == 650
    assert entry["return_pct"] == 3.86
    # created_at is ISO 8601 string
    assert isinstance(entry["created_at"], str)
    assert "T" in entry["created_at"]


def test_summary_uses_latest_return_pct(db_session):
    portfolio = Portfolio(name="Test")
    db_session.add(portfolio)
    db_session.flush()

    _add_snapshot(db_session, portfolio.id, 16850, 16850, 0.0)
    _add_snapshot(db_session, portfolio.id, 17475, 16850, 3.71)
    _add_snapshot(db_session, portfolio.id, 18375, 17450, 5.30)

    db_session.commit()

    summary = get_historical_summary(db_session, portfolio.id)

    assert summary["snapshot_count"] == 3
    assert summary["current_value"] == 18375
    assert summary["first_value"] == 16850
    # total_return_pct = latest snapshot's own return_pct
    assert summary["total_return_pct"] == 5.30
    # latest snapshot id should be the third one
    history = get_snapshot_history(db_session, portfolio.id)
    assert summary["latest_snapshot_id"] == history[-1]["snapshot_id"]


def test_history_only_includes_own_portfolio(db_session):
    p1 = Portfolio(name="A")
    p2 = Portfolio(name="B")
    db_session.add_all([p1, p2])
    db_session.flush()

    _add_snapshot(db_session, p1.id, 10000, 10000, 0.0)
    _add_snapshot(db_session, p1.id, 11000, 10000, 10.0)
    _add_snapshot(db_session, p2.id, 20000, 20000, 0.0)

    db_session.commit()

    h1 = get_snapshot_history(db_session, p1.id)
    h2 = get_snapshot_history(db_session, p2.id)

    assert len(h1) == 2
    assert len(h2) == 1
    assert h2[0]["portfolio_value"] == 20000