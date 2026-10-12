import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents.tools import (
    build_fallback,
    collect_fact_numbers,
    extract_numbers,
    gather_evidence,
    validate_numbers,
)
from app.database.models import Base, Holding, Portfolio, Snapshot


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


# =========================================================
# extract_numbers
# =========================================================

def test_extract_numbers_basic():
    result = extract_numbers("NVDA added +1.78% while GOOGL dropped 0.30pp")
    assert result == [1.78, 0.30]


def test_extract_numbers_currency():
    result = extract_numbers("worth $17,475.00")
    # "$17,475.00" -> 17475.00
    assert 17475.0 in result


def test_extract_numbers_empty():
    assert extract_numbers("") == []
    assert extract_numbers(None) == []


def test_extract_numbers_negative():
    result = extract_numbers("down -2.08%")
    assert -2.08 in result


# =========================================================
# validate_numbers
# =========================================================

def _evidence(**overrides):
    base = {
        "portfolio_id": 1,
        "snapshot_id": 12,
        "return_pct": 3.71,
        "portfolio_value": 17475.00,
        "top_contributor": {
            "ticker": "NVDA",
            "contribution_pct": 1.78,
            "return_pct": 9.09,
            "pnl": 300,
            "weight_pct": 20.60,
            "sector": "Semiconductors",
        },
        "top_detractor": {
            "ticker": "GOOGL",
            "contribution_pct": -0.30,
            "return_pct": -2.08,
            "pnl": -50,
            "weight_pct": 13.45,
            "sector": "Technology",
        },
        "all_contributors": [],
        "all_detractors": [],
        "leading_sector": {
            "sector": "Semiconductors",
            "contribution_pct": 2.67,
            "return_pct": 6.62,
            "weight_pct": 41.49,
            "holdings": ["AVGO", "NVDA"],
        },
        "lagging_sector": None,
        "all_sectors": [],
        "deterministic_explanation": "",
    }
    base.update(overrides)
    return base


def test_validate_numbers_known_pass():
    evidence = _evidence()
    text = "Your portfolio is up +3.71%, worth $17,475.00. NVDA contributed +1.78pp."
    result = validate_numbers(text, evidence)
    assert result["valid"] is True
    assert result["unknown"] == []


def test_validate_numbers_invented_fails():
    evidence = _evidence()
    text = "Your portfolio is up +3.71%, with NVDA contributing +5.99pp."
    result = validate_numbers(text, evidence)
    assert result["valid"] is False
    assert 5.99 in result["unknown"]


def test_validate_numbers_ignores_small_integers():
    evidence = _evidence()
    text = "The top 3 holdings drove most of the move."
    result = validate_numbers(text, evidence)
    assert result["valid"] is True


def test_validate_numbers_empty_text():
    evidence = _evidence()
    result = validate_numbers("", evidence)
    assert result["valid"] is False


# =========================================================
# gather_evidence (needs DB)
# =========================================================

def _make_portfolio(db):
    p = Portfolio(name="Test")
    db.add(p)
    db.flush()
    return p


def _make_snapshot(db, portfolio_id, value=17475, cost=16850, ret=3.71):
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


def _make_holding(db, snapshot_id, ticker, shares, avg, cur, sector, wpct, cpct):
    pv = shares * cur
    cb = shares * avg
    h = Holding(
        snapshot_id=snapshot_id,
        ticker=ticker,
        shares=shares,
        avg_price=avg,
        current_price=cur,
        sector=sector,
        position_value=pv,
        cost_basis=cb,
        pnl=pv - cb,
        return_pct=((cur - avg) / avg) * 100,
        weight_pct=wpct,
        contribution_pct=cpct,
    )
    db.add(h)
    db.flush()
    return h


def test_gather_evidence_no_snapshots(db_session):
    portfolio = _make_portfolio(db_session)
    evidence = gather_evidence(db_session, portfolio.id)
    assert evidence is None


def test_gather_evidence_full(db_session):
    portfolio = _make_portfolio(db_session)
    snapshot = _make_snapshot(db_session, portfolio.id)

    _make_holding(db_session, snapshot.id, "NVDA", 20, 165, 180, "Semiconductors", 20.60, 1.78)
    _make_holding(db_session, snapshot.id, "MSFT", 15, 510, 525, "Technology", 45.06, 1.34)
    _make_holding(db_session, snapshot.id, "AVGO", 10, 350, 365, "Semiconductors", 20.89, 0.89)
    _make_holding(db_session, snapshot.id, "GOOGL", 10, 240, 235, "Technology", 13.45, -0.30)

    db_session.commit()

    evidence = gather_evidence(db_session, portfolio.id)

    assert evidence is not None
    assert evidence["portfolio_id"] == portfolio.id
    assert evidence["snapshot_id"] == snapshot.id
    assert evidence["return_pct"] == 3.71

    # Top contributor should be NVDA
    assert evidence["top_contributor"]["ticker"] == "NVDA"
    assert evidence["top_contributor"]["contribution_pct"] == 1.78

    # Top detractor should be GOOGL
    assert evidence["top_detractor"]["ticker"] == "GOOGL"
    assert evidence["top_detractor"]["contribution_pct"] == -0.30

    # Leading sector should be Semiconductors
    assert evidence["leading_sector"]["sector"] == "Semiconductors"
    assert evidence["leading_sector"]["contribution_pct"] > 0

    # No lagging sector (all sectors positive)
    assert evidence["lagging_sector"] is None


def test_gather_evidence_handles_unclassified_sector(db_session):
    portfolio = _make_portfolio(db_session)
    snapshot = _make_snapshot(db_session, portfolio.id)

    _make_holding(db_session, snapshot.id, "XYZ", 10, 100, 110, None, 100.0, 1.0)
    db_session.commit()

    evidence = gather_evidence(db_session, portfolio.id)

    assert evidence is not None
    # Sector should be normalized to "Unclassified"
    assert evidence["top_contributor"]["sector"] == "Unclassified"


# =========================================================
# build_fallback
# =========================================================

def test_build_fallback():
    evidence = _evidence(deterministic_explanation="Deterministic text.")
    result = build_fallback(evidence)
    assert result["explanation"] == "Deterministic text."
    assert result["source"] == "deterministic_fallback"
    assert result["validation"]["valid"] is True


def test_collect_fact_numbers():
    evidence = _evidence()
    facts = collect_fact_numbers(evidence)
    assert 3.71 in facts
    assert 1.78 in facts
    assert 0.30 in facts  # absolute value of -0.30 also stored