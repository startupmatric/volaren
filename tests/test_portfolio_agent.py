"""
Tests for the LangGraph portfolio agent.

The LLM is mocked so tests are fast, free, and deterministic.
We test the graph logic and the fallback behavior, not the LLM itself.
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.agents import portfolio_agent
from app.database.models import Base, Holding, Portfolio, Snapshot


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _seed(db, return_pct=3.71):
    """Insert one portfolio with 2 holdings."""
    p = Portfolio(name="Test")
    db.add(p)
    db.flush()

    s = Snapshot(
        portfolio_id=p.id,
        portfolio_value=17475,
        cost_basis=16850,
        pnl=625,
        return_pct=return_pct,
    )
    db.add(s)
    db.flush()

    for ticker, shares, avg, cur, sector, wpct, cpct in [
        ("NVDA", 20, 165, 180, "Semiconductors", 20.60, 1.78),
        ("GOOGL", 10, 240, 235, "Technology", 13.45, -0.30),
    ]:
        pv = shares * cur
        cb = shares * avg
        db.add(Holding(
            snapshot_id=s.id,
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
        ))

    db.commit()
    return p


def _mock_llm_response(text):
    """Build a fake response object that matches langchain_core's shape."""
    response = MagicMock()
    response.content = text
    return response


def _patch_chat_groq(text):
    """
    Patch ChatGroq so any .invoke() call returns our canned response.
    """
    fake_client = MagicMock()
    fake_client.invoke.return_value = _mock_llm_response(text)

    return patch.object(
        portfolio_agent,
        "ChatGroq",
        return_value=fake_client,
    )


def test_agent_returns_none_for_empty_portfolio(db_session):
    p = Portfolio(name="Empty")
    db_session.add(p)
    db_session.commit()

    with _patch_chat_groq("irrelevant"):
        result = portfolio_agent.run_agent(db_session, p.id)

    assert result is None


def test_agent_uses_llm_when_output_is_valid(db_session):
    portfolio = _seed(db_session)

    good_text = (
        "Your portfolio is up +3.71%. NVDA contributed +1.78pp "
        "while GOOGL dragged -0.30pp."
    )

    with _patch_chat_groq(good_text):
        result = portfolio_agent.run_agent(db_session, portfolio.id)

    assert result is not None
    assert result["source"] == "llm"
    assert result["validation"]["valid"] is True
    assert "NVDA" in result["explanation"]


def test_agent_falls_back_when_llm_invents_number(db_session):
    portfolio = _seed(db_session)

    bad_text = (
        "Your portfolio is up +3.71%. NVDA contributed +5.99pp to returns."
    )

    with _patch_chat_groq(bad_text):
        result = portfolio_agent.run_agent(db_session, portfolio.id)

    assert result is not None
    assert result["source"] == "deterministic_fallback"
    assert result["explanation"] != bad_text
    assert "NVDA is the biggest contributor" in result["explanation"]


def test_agent_falls_back_when_llm_raises(db_session):
    portfolio = _seed(db_session)

    fake_client = MagicMock()
    fake_client.invoke.side_effect = RuntimeError("Simulated network error")

    with patch.object(
        portfolio_agent,
        "ChatGroq",
        return_value=fake_client,
    ):
        result = portfolio_agent.run_agent(db_session, portfolio.id)

    assert result is not None
    assert result["source"] == "deterministic_fallback"
    assert "Your portfolio is up +3.71%" in result["explanation"]


def test_agent_handles_empty_llm_response(db_session):
    portfolio = _seed(db_session)

    with _patch_chat_groq(""):
        result = portfolio_agent.run_agent(db_session, portfolio.id)

    assert result is not None
    assert result["source"] == "deterministic_fallback"


def test_agent_graph_has_expected_nodes():
    """
    Structural test: verify the graph builds without error and
    returns something with an invoke method.

    We patch ChatGroq so the test doesn't need a real API key.
    """

    fake_db = MagicMock()

    with _patch_chat_groq(""):
        graph = portfolio_agent.build_agent_graph(fake_db)

    assert hasattr(graph, "invoke")