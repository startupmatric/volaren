import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, Holding, Portfolio, Snapshot
from app.services.diff_service import compute_diff


@pytest.fixture
def db_session():
    """In-memory SQLite for isolated diff tests."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    yield session

    session.close()


def _make_holding(ticker, shares, avg_price, current_price, snapshot_id):
    position_value = shares * current_price
    cost_basis = shares * avg_price
    return Holding(
        snapshot_id=snapshot_id,
        ticker=ticker,
        shares=shares,
        avg_price=avg_price,
        current_price=current_price,
        sector="Test",
        position_value=position_value,
        cost_basis=cost_basis,
        pnl=position_value - cost_basis,
        return_pct=((current_price - avg_price) / avg_price) * 100,
        weight_pct=0.0,
        contribution_pct=0.0,
    )


def test_diff_needs_two_snapshots(db_session):
    portfolio = Portfolio(name="Test")
    db_session.add(portfolio)
    db_session.flush()

    snap = Snapshot(
        portfolio_id=portfolio.id,
        portfolio_value=1000,
        cost_basis=1000,
        pnl=0,
        return_pct=0,
    )
    db_session.add(snap)
    db_session.commit()

    assert compute_diff(db_session, portfolio.id) is None


def test_diff_computes_new_and_closed_positions(db_session):
    portfolio = Portfolio(name="Test")
    db_session.add(portfolio)
    db_session.flush()

    # Snapshot 1: NVDA, GOOGL
    s1 = Snapshot(
        portfolio_id=portfolio.id,
        portfolio_value=10000,
        cost_basis=9000,
        pnl=1000,
        return_pct=11.11,
    )
    db_session.add(s1)
    db_session.flush()
    db_session.add(_make_holding("NVDA", 10, 100, 150, s1.id))
    db_session.add(_make_holding("GOOGL", 10, 200, 250, s1.id))

    # Snapshot 2 (later): NVDA, AMD
    s2 = Snapshot(
        portfolio_id=portfolio.id,
        portfolio_value=12000,
        cost_basis=10000,
        pnl=2000,
        return_pct=20.0,
    )
    db_session.add(s2)
    db_session.flush()
    db_session.add(_make_holding("NVDA", 10, 100, 180, s2.id))
    db_session.add(_make_holding("AMD", 20, 80, 90, s2.id))

    db_session.commit()

    diff = compute_diff(db_session, portfolio.id)

    assert diff is not None
    assert diff["previous_snapshot_id"] == s1.id
    assert diff["latest_snapshot_id"] == s2.id

    assert diff["new_positions"] == ["AMD"]
    assert diff["closed_positions"] == ["GOOGL"]

    assert diff["portfolio_value_delta"] == 2000
    assert diff["return_pct_delta"] == 8.89


def test_diff_weight_changes_sorted_by_absolute_delta(db_session):
    portfolio = Portfolio(name="Test")
    db_session.add(portfolio)
    db_session.flush()

    s1 = Snapshot(
        portfolio_id=portfolio.id,
        portfolio_value=10000,
        cost_basis=9000,
        pnl=1000,
        return_pct=11.11,
    )
    db_session.add(s1)
    db_session.flush()

    h1_a = _make_holding("AAA", 10, 100, 150, s1.id)
    h1_a.weight_pct = 30.0
    h1_b = _make_holding("BBB", 10, 100, 150, s1.id)
    h1_b.weight_pct = 50.0
    h1_c = _make_holding("CCC", 10, 100, 150, s1.id)
    h1_c.weight_pct = 20.0
    db_session.add_all([h1_a, h1_b, h1_c])

    s2 = Snapshot(
        portfolio_id=portfolio.id,
        portfolio_value=12000,
        cost_basis=10000,
        pnl=2000,
        return_pct=20.0,
    )
    db_session.add(s2)
    db_session.flush()

    h2_a = _make_holding("AAA", 10, 100, 150, s2.id)
    h2_a.weight_pct = 10.0  # -20
    h2_b = _make_holding("BBB", 10, 100, 150, s2.id)
    h2_b.weight_pct = 55.0  # +5
    h2_c = _make_holding("CCC", 10, 100, 150, s2.id)
    h2_c.weight_pct = 35.0  # +15
    db_session.add_all([h2_a, h2_b, h2_c])

    db_session.commit()

    diff = compute_diff(db_session, portfolio.id)

    order = [w["ticker"] for w in diff["weight_changes"]]

    # AAA has largest absolute delta (-20), then CCC (+15), then BBB (+5)
    assert order == ["AAA", "CCC", "BBB"]