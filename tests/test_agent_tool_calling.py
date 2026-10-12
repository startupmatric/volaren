"""
Tests for the tool-calling agent graph.

We mock ChatGroq (deterministic responses) and route the tools to
the test's SQLite session via `SessionLocal` patching.

The graph runs for real: agent, ToolNode, router, validate, finalize.

Note: SQLite in-memory needs `check_same_thread=False` + `StaticPool`
because LangGraph may run nodes in threads that differ from the
pytest main thread.
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


def _seed(db):
    p = Portfolio(name="Test")
    db.add(p)
    db.flush()

    s = Snapshot(
        portfolio_id=p.id,
        portfolio_value=17475,
        cost_basis=16850,
        pnl=625,
        return_pct=3.71,
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


class FakeLLM:
    def __init__(self, responses):
        self.responses = responses
        self.call_count = 0

    def invoke(self, messages):
        idx = min(self.call_count, len(self.responses) - 1)
        self.call_count += 1
        return self.responses[idx]

    def bind_tools(self, tools):
        return self


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


def _patch_llm(responses):
    fake = FakeLLM(responses)

    def factory(*args, **kwargs):
        return fake

    return patch.object(portfolio_agent, "ChatGroq", side_effect=factory)


def _patch_session_local(db):
    return patch(
        "app.database.session.SessionLocal",
        return_value=db,
    )


def test_agent_returns_none_for_empty_portfolio(db_session):
    p = Portfolio(name="Empty")
    db_session.add(p)
    db_session.commit()

    with _patch_llm([_final_msg("unused")]), _patch_session_local(db_session):
        result = portfolio_agent.run_agent(db_session, p.id)

    assert result is None


def test_agent_runs_tools_and_returns_explanation(db_session):
    portfolio = _seed(db_session)

    responses = [
        _tool_call_msg("get_portfolio_movers", {"portfolio_id": portfolio.id}, "c1"),
        _tool_call_msg("get_portfolio_summary", {"portfolio_id": portfolio.id}, "c2"),
        _final_msg("Your portfolio is up +3.71%."),
    ]

    with _patch_llm(responses), _patch_session_local(db_session):
        result = portfolio_agent.run_agent(db_session, portfolio.id)

    assert result is not None
    assert result["source"] in ("llm", "deterministic_fallback")
    assert result["explanation"]

    called_names = [tc["name"] for tc in result["tool_calls"]]
    assert "get_portfolio_movers" in called_names
    assert "get_portfolio_summary" in called_names


def test_agent_falls_back_gracefully_when_llm_raises(db_session):
    portfolio = _seed(db_session)

    fake = MagicMock()
    fake.invoke.side_effect = RuntimeError("Simulated LLM failure")
    fake.bind_tools.return_value = fake

    def factory(*args, **kwargs):
        return fake

    with patch.object(portfolio_agent, "ChatGroq", side_effect=factory), \
         _patch_session_local(db_session):
        result = portfolio_agent.run_agent(db_session, portfolio.id)

    assert result is not None
    assert result["source"] == "deterministic_fallback"


def test_agent_records_tool_call_args(db_session):
    portfolio = _seed(db_session)

    responses = [
        _tool_call_msg("get_portfolio_movers", {"portfolio_id": portfolio.id}, "c1"),
        _final_msg("Your portfolio is up +3.71%."),
    ]

    with _patch_llm(responses), _patch_session_local(db_session):
        result = portfolio_agent.run_agent(db_session, portfolio.id)

    assert result is not None
    assert len(result["tool_calls"]) >= 1

    first = result["tool_calls"][0]
    assert first["name"] == "get_portfolio_movers"
    assert first["args"] == {"portfolio_id": portfolio.id}
    assert first["latency_ms"] >= 0