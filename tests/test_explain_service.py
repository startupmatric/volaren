import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, Holding, Portfolio, Snapshot
from app.services.explain_service import explain_attribution


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _scaffold(db, holdings, return_pct=3.71, value=17475, cost=16850):
    p = Portfolio(name="Test")
    db.add(p)
    db.flush()

    s = Snapshot(
        portfolio_id=p.id,
        portfolio_value=value,
        cost_basis=cost,
        pnl=value - cost,
        return_pct=return_pct,
    )
    db.add(s)
    db.flush()

    for h in holdings:
        ticker, shares, avg, cur, sector, wpct, cpct = h

        position_value = shares * cur
        cost_basis = shares * avg
        pnl = position_value - cost_basis

        db.add(Holding(
            snapshot_id=s.id,
            ticker=ticker,
            shares=shares,
            avg_price=avg,
            current_price=cur,
            sector=sector,
            position_value=position_value,
            cost_basis=cost_basis,
            pnl=pnl,
            return_pct=((cur - avg) / avg) * 100,
            weight_pct=wpct,
            contribution_pct=cpct,
        ))

    db.flush()
    return p


def test_explain_returns_none_for_empty_portfolio(db_session):
    p = Portfolio(name="Empty")
    db_session.add(p)
    db_session.flush()

    result = explain_attribution(db_session, p.id)

    assert result is None


def test_explain_produces_headline_and_explanation(db_session):
    portfolio = _scaffold(db_session, [
        ("NVDA", 20, 165, 180, "Semiconductors", 20.6, 1.78),
        ("GOOGL", 10, 240, 235, "Technology", 13.45, -0.30),
    ])

    result = explain_attribution(db_session, portfolio.id)

    assert result is not None
    assert "up" in result["headline"]
    assert "3.71%" in result["headline"]
    assert len(result["sentences"]) >= 1
    assert result["explanation"] == " ".join(result["sentences"])


def test_explain_mentions_contributor(db_session):
    portfolio = _scaffold(db_session, [
        ("NVDA", 20, 165, 180, "Semiconductors", 20.6, 1.78),
    ])

    result = explain_attribution(db_session, portfolio.id)

    assert "NVDA" in result["explanation"]


def test_explain_mentions_detractor_when_negative(db_session):
    portfolio = _scaffold(db_session, [
        ("NVDA", 20, 165, 180, "Semiconductors", 20.6, 1.78),
        ("GOOGL", 10, 240, 235, "Technology", 13.45, -0.30),
    ])

    result = explain_attribution(db_session, portfolio.id)

    assert "GOOGL" in result["explanation"]
    # "subtracting" should be followed by a number, not "+number"
    assert "subtracting 0.30pp" in result["explanation"]
    assert "subtracting +0.30pp" not in result["explanation"]


def test_explain_sectors_mention(db_session):
    portfolio = _scaffold(db_session, [
        ("NVDA", 20, 165, 180, "Semiconductors", 20.6, 1.78),
        ("AVGO", 10, 350, 365, "Semiconductors", 20.89, 0.89),
        ("MSFT", 15, 510, 525, "Technology", 45.06, 1.34),
    ])

    result = explain_attribution(db_session, portfolio.id)

    assert "Semiconductors" in result["explanation"]


def test_explain_flat_portfolio(db_session):
    portfolio = _scaffold(
        db_session,
        [("AAA", 10, 100, 100, "Test", 100.0, 0.0)],
        return_pct=0.0,
        value=1000,
        cost=1000,
    )

    result = explain_attribution(db_session, portfolio.id)

    assert "flat" in result["headline"]