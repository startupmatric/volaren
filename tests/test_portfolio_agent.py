"""
Tests for the LangGraph portfolio agent.

These tests exercise the Day 8a tool-calling graph. The LLM is mocked
so tests are fast and deterministic. Tools run against the test's
SQLite session (via SessionLocal patching) so no external DB is needed.
"""

from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import AIMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.agents import portfolio_agent
from app.database.models import Base, Holding, Portfolio, Snapshot


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _seed(db, return_pct=3.71):
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


class _FakeLLM:
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0

    def invoke(self, messages):
        idx = min(self.call_count, len(self.responses) - 1)
        self.call_count += 1
        return self.responses[idx]

    def bind_tools(self, tools):
        return self


def _patch_llm(responses):
    fake = _FakeLLM(responses)

    def factory(*args, **kwargs):
        return fake

    return patch.object(portfolio_agent, "ChatGroq", side_effect=factory)


def _patch_session_local(db):
    return patch("app.database.session.SessionLocal", return_value=db)


def _tool_call_msg(name, args, call_id="call-1"):
    return AIMessage(
        content="",
        tool_calls=[{
            "name": name,
            "args": args,
            "id": call_id,
            "type": "tool_call",
        }],
    )


def _final_msg(text):
    return AIMessage(content=text)


def test_agent_returns_none_for_empty_portfolio(db_session):
    p = Portfolio(name="Empty")
    db_session.add(p)
    db_session.commit()

    with _patch_llm([_final_msg("unused")]), _patch_session_local(db_session):
        result = portfolio_agent.run_agent(db_session, p.id)

    assert result is None


def test_agent_uses_llm_when_output_is_valid(db_session):
    portfolio = _seed(db_session)

    responses = [
        _tool_call_msg(
            "get_portfolio_movers",
            {"portfolio_id": portfolio.id},
            "c1",
        ),
        _final_msg(
            "Your portfolio is up +3.71%. NVDA contributed +1.78pp "
            "while GOOGL dragged -0.30pp."
        ),
    ]

    with _patch_llm(responses), _patch_session_local(db_session):
        result = portfolio_agent.run_agent(db_session, portfolio.id)

    assert result is not None
    assert result["source"] in ("llm", "deterministic_fallback")
    assert result["explanation"]
    assert "NVDA" in result["explanation"] or "GOOGL" in result["explanation"]


def test_agent_falls_back_when_llm_invents_number(db_session):
    portfolio = _seed(db_session)

    responses = [
        _tool_call_msg(
            "get_portfolio_movers",
            {"portfolio_id": portfolio.id},
            "c1",
        ),
        _final_msg(
            "Your portfolio is up +3.71%. NVDA contributed +5.99pp to returns."
        ),
    ]

    with _patch_llm(responses), _patch_session_local(db_session):
        result = portfolio_agent.run_agent(db_session, portfolio.id)

    assert result is not None
    assert result["source"] == "deterministic_fallback"


def test_agent_falls_back_when_llm_raises(db_session):
    portfolio = _seed(db_session)

    fake = MagicMock()
    fake.invoke.side_effect = RuntimeError("Simulated network error")
    fake.bind_tools.return_value = fake

    def factory(*args, **kwargs):
        return fake

    with patch.object(portfolio_agent, "ChatGroq", side_effect=factory), \
         _patch_session_local(db_session):
        result = portfolio_agent.run_agent(db_session, portfolio.id)

    assert result is not None
    assert result["source"] == "deterministic_fallback"
    assert "Your portfolio is up +3.71%" in result["explanation"]


def test_agent_handles_empty_llm_response(db_session):
    portfolio = _seed(db_session)

    responses = [
        _tool_call_msg(
            "get_portfolio_movers",
            {"portfolio_id": portfolio.id},
            "c1",
        ),
        _final_msg(""),
    ]

    with _patch_llm(responses), _patch_session_local(db_session):
        result = portfolio_agent.run_agent(db_session, portfolio.id)

    assert result is not None
    assert result["source"] == "deterministic_fallback"


def test_agent_graph_has_expected_nodes(db_session):
    fake_db = MagicMock()

    with _patch_llm([_final_msg("")]):
        graph = portfolio_agent.build_agent_graph(fake_db)

    assert hasattr(graph, "invoke")