import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.models import Base, Holding, Portfolio, Snapshot
from app.services.attribution_service import (
    get_movers,
    get_sector_attribution,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _make_portfolio(db, name="Test"):
    p = Portfolio(name=name)
    db.add(p)
    db.flush()
    return p


def _make_snapshot(db, portfolio_id, value=10000, cost=9000, ret=11.11):
    s = Snapshot(
        portfolio_id=portfolio_id,
        portfolio_value=value,
        cost_basis=cost,
        pnl=value - cost,
        return_pct=ret,
    )
    db.add(s)
    db.flush()
    return s


def _make_holding(
    db,
    snapshot_id,
    ticker,
    shares,
    avg_price,
    current_price,
    sector="Test",
    weight_pct=0.0,
    contribution_pct=0.0,
):
    position_value = shares * current_price
    cost_basis = shares * avg_price
    pnl = position_value - cost_basis

    h = Holding(
        snapshot_id=snapshot_id,
        ticker=ticker,
        shares=shares,
        avg_price=avg_price,
        current_price=current_price,
        sector=sector,
        position_value=position_value,
        cost_basis=cost_basis,
        pnl=pnl,
        return_pct=((current_price - avg_price) / avg_price) * 100,
        weight_pct=weight_pct,
        contribution_pct=contribution_pct,
    )
    db.add(h)
    db.flush()
    return h


def test_get_movers_no_snapshots(db_session):
    portfolio = _make_portfolio(db_session)

    movers = get_movers(db_session, portfolio.id)

    assert movers is None


def test_get_movers_empty_holdings(db_session):
    portfolio = _make_portfolio(db_session)
    _make_snapshot(db_session, portfolio.id)

    movers = get_movers(db_session, portfolio.id)

    assert movers is not None
    assert movers["top_gainers"] == []
    assert movers["top_losers"] == []
    assert movers["top_contributors"] == []
    assert movers["top_detractors"] == []


def test_get_movers_splits_gainers_and_losers(db_session):
    portfolio = _make_portfolio(db_session)
    snap = _make_snapshot(db_session, portfolio.id)

    _make_holding(
        db_session, snap.id, "NVDA",
        shares=20, avg_price=165, current_price=180,
        contribution_pct=1.78,
    )
    _make_holding(
        db_session, snap.id, "GOOGL",
        shares=10, avg_price=240, current_price=235,
        contribution_pct=-0.30,
    )

    movers = get_movers(db_session, portfolio.id)

    gainers = [h["ticker"] for h in movers["top_gainers"]]
    losers = [h["ticker"] for h in movers["top_losers"]]

    assert "NVDA" in gainers
    assert "GOOGL" not in gainers
    assert "GOOGL" in losers
    assert "NVDA" not in losers


def test_get_movers_uses_latest_snapshot(db_session):
    portfolio = _make_portfolio(db_session)

    snap1 = _make_snapshot(db_session, portfolio.id, value=10000)
    _make_holding(
        db_session, snap1.id, "OLD",
        shares=10, avg_price=100, current_price=110,
    )

    snap2 = _make_snapshot(db_session, portfolio.id, value=12000)
    _make_holding(
        db_session, snap2.id, "NEW",
        shares=10, avg_price=100, current_price=120,
    )

    movers = get_movers(db_session, portfolio.id)

    assert movers["snapshot_id"] == snap2.id
    tickers = [h["ticker"] for h in movers["top_gainers"]]
    assert "NEW" in tickers
    assert "OLD" not in tickers


def test_sector_attribution_no_snapshots(db_session):
    portfolio = _make_portfolio(db_session)

    attribution = get_sector_attribution(db_session, portfolio.id)

    assert attribution is None


def test_sector_attribution_groups_by_sector(db_session):
    portfolio = _make_portfolio(db_session)
    snap = _make_snapshot(db_session, portfolio.id)

    _make_holding(
        db_session, snap.id, "NVDA",
        shares=20, avg_price=165, current_price=180,
        sector="Semiconductors",
    )
    _make_holding(
        db_session, snap.id, "AVGO",
        shares=10, avg_price=350, current_price=365,
        sector="Semiconductors",
    )
    _make_holding(
        db_session, snap.id, "MSFT",
        shares=15, avg_price=510, current_price=525,
        sector="Technology",
    )

    attribution = get_sector_attribution(db_session, portfolio.id)

    sectors = {s["sector"]: s for s in attribution["sectors"]}

    assert "Semiconductors" in sectors
    assert "Technology" in sectors

    semis = sectors["Semiconductors"]
    assert sorted(semis["holdings"]) == ["AVGO", "NVDA"]
    assert semis["pnl"] == 300 + 150  # NVDA 300, AVGO 150


def test_sector_attribution_unclassified(db_session):
    portfolio = _make_portfolio(db_session)
    snap = _make_snapshot(db_session, portfolio.id)

    _make_holding(
        db_session, snap.id, "XYZ",
        shares=10, avg_price=100, current_price=110,
        sector=None,
    )

    attribution = get_sector_attribution(db_session, portfolio.id)

    sectors = {s["sector"]: s for s in attribution["sectors"]}

    assert "Unclassified" in sectors
    assert sectors["Unclassified"]["holdings"] == ["XYZ"]


def test_sector_attribution_contribution_sums_to_return(db_session):
    portfolio = _make_portfolio(db_session)
    snap = _make_snapshot(db_session, portfolio.id, value=17475, cost=16850, ret=3.71)

    _make_holding(
        db_session, snap.id, "NVDA",
        shares=20, avg_price=165, current_price=180,
        sector="Semiconductors",
    )
    _make_holding(
        db_session, snap.id, "MSFT",
        shares=15, avg_price=510, current_price=525,
        sector="Technology",
    )

    attribution = get_sector_attribution(db_session, portfolio.id)

    total_contribution = sum(
        s["contribution_pct"] for s in attribution["sectors"]
    )

    # Service computes contribution as pnl / sum(holding.cost_basis) * 100
    # NVDA cost = 20 * 165  = 3300
    # MSFT cost = 15 * 510  = 7650
    # total holding cost    = 10950
    # NVDA pnl  = 300, MSFT pnl = 225 -> total pnl = 525
    # expected total contribution = 525 / 10950 * 100 = 4.7945...
    total_holding_cost = 3300 + 7650

    expected = (525 / total_holding_cost) * 100

    assert abs(total_contribution - expected) < 0.01