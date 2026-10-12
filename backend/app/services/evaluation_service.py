"""
Evaluation service.

Runs the agent (deterministic OR LLM) on a real portfolio and
evaluates the resulting explanation against the actual evidence.

This is the glue between:
  - agents/tools.py  (evidence gathering)
  - agents/portfolio_agent.py  (LLM + tool-calling reasoning)
  - services/explain_service.py  (deterministic text)
  - evaluation/evaluator.py  (scoring + tool coverage)

The report shape is stable — the API wraps it directly.
"""

import time
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.agents.tool_registry import INTENT_EXPLAIN_MOVEMENT
from app.agents.tools import gather_evidence
from app.evaluation.evaluator import (
    evaluate_explanation,
    evaluate_tool_coverage,
)
from app.services.explain_service import explain_attribution


# =========================================================
# HELPERS
# =========================================================

def _build_case_from_evidence(
    evidence: dict,
    explanation: str,
) -> dict:
    """
    Wrap a real portfolio's evidence in the same shape as a
    golden case, so we can reuse evaluate_explanation.
    """

    expected = {
        "portfolio_return": evidence.get("return_pct"),
    }

    top_contributor = evidence.get("top_contributor")
    if top_contributor:
        expected["top_contributor"] = top_contributor.get("ticker")

    top_detractor = evidence.get("top_detractor")
    if top_detractor:
        expected["top_detractor"] = top_detractor.get("ticker")

    leading_sector = evidence.get("leading_sector")
    if leading_sector:
        expected["leading_sector"] = leading_sector.get("sector")

    lagging_sector = evidence.get("lagging_sector")
    if lagging_sector:
        expected["lagging_sector"] = lagging_sector.get("sector")

    return {
        "name": f"portfolio_{evidence.get('portfolio_id')}",
        "evidence": evidence,
        "expected": expected,
    }


def _build_report(
    portfolio_id: int,
    snapshot_id: Optional[int],
    source: str,
    explanation: str,
    evaluation: dict,
    latency_ms: float,
    tool_calls: Optional[list] = None,
    tool_coverage: Optional[dict] = None,
) -> dict:
    return {
        "portfolio_id": portfolio_id,
        "snapshot_id": snapshot_id,
        "source": source,
        "latency_ms": round(latency_ms, 2),
        "passed": evaluation.get("passed", False),
        "scores": evaluation.get("scores", {}),
        "unsupported_numbers": evaluation.get("unsupported_numbers", []),
        "unsupported_tickers": evaluation.get("unsupported_tickers", []),
        "missing_expected_facts": evaluation.get("missing_expected_facts", {}),
        "found_expected_facts": evaluation.get("found_expected_facts", {}),
        "explanation": explanation,
        "tool_calls": tool_calls or [],
        "tool_coverage": tool_coverage or {
            "intent": None,
            "required": [],
            "called": [],
            "missing": [],
            "satisfied": True,
            "coverage": 1.0,
        },
    }


# =========================================================
# DETERMINISTIC MODE
# =========================================================

def evaluate_portfolio_deterministic(
    db: Session,
    portfolio_id: int,
) -> Optional[dict]:
    """
    Evaluate the *deterministic* explanation for a real portfolio.

    Fast, free, no LLM. Useful as a baseline and for tests.

    Returns None if the portfolio has no snapshots.
    """

    evidence = gather_evidence(db, portfolio_id)

    if evidence is None:
        return None

    started_at = time.perf_counter()

    explain_result = explain_attribution(db, portfolio_id)

    if explain_result is None:
        return None

    explanation = explain_result.get("explanation", "")

    case = _build_case_from_evidence(evidence, explanation)

    evaluation = evaluate_explanation(explanation, case)

    elapsed_ms = (time.perf_counter() - started_at) * 1000

    return _build_report(
        portfolio_id=portfolio_id,
        snapshot_id=evidence.get("snapshot_id"),
        source="deterministic",
        explanation=explanation,
        evaluation=evaluation,
        latency_ms=elapsed_ms,
        tool_calls=[],
        tool_coverage=None,
    )


# =========================================================
# AGENT MODE
# =========================================================

def evaluate_portfolio_with_agent(
    db: Session,
    portfolio_id: int,
    intent: str = INTENT_EXPLAIN_MOVEMENT,
) -> Optional[dict]:
    """
    Evaluate the LLM explanation for a real portfolio,
    including tool selection.

    Falls back gracefully when the LLM is unavailable.

    Returns None if the portfolio has no snapshots.
    """

    evidence = gather_evidence(db, portfolio_id)

    if evidence is None:
        return None

    started_at = time.perf_counter()

    # Use the tool-calling agent directly so we capture tool_calls
    from app.agents.portfolio_agent import run_agent

    agent_result = run_agent(db, portfolio_id, intent=intent)

    if agent_result is None:
        return None

    explanation = agent_result.get("explanation", "")
    source = agent_result.get("source", "unknown")
    tool_calls = agent_result.get("tool_calls") or []

    case = _build_case_from_evidence(evidence, explanation)

    evaluation = evaluate_explanation(explanation, case)

    # If the LLM failed and we fell back, this is a soft failure.
    if source == "deterministic_fallback":
        evaluation["passed"] = False
        evaluation.setdefault("reason", "llm_fallback")

    # Score tool coverage
    tool_coverage = evaluate_tool_coverage(intent, tool_calls)

    # If tools were required and missing, penalize the pass
    if not tool_coverage.get("satisfied", True):
        evaluation["passed"] = False
        evaluation.setdefault("reason", "missing_required_tools")

    elapsed_ms = (time.perf_counter() - started_at) * 1000

    return _build_report(
        portfolio_id=portfolio_id,
        snapshot_id=evidence.get("snapshot_id"),
        source=source,
        explanation=explanation,
        evaluation=evaluation,
        latency_ms=elapsed_ms,
        tool_calls=tool_calls,
        tool_coverage=tool_coverage,
    )


# =========================================================
# UNIFIED ENTRY POINT
# =========================================================

def evaluate_portfolio(
    db: Session,
    portfolio_id: int,
    mode: str = "deterministic",
    intent: str = INTENT_EXPLAIN_MOVEMENT,
) -> Optional[dict]:
    """
    Unified entry point.

    mode = "deterministic" | "agent"
    """

    if mode == "agent":
        return evaluate_portfolio_with_agent(
            db,
            portfolio_id,
            intent=intent,
        )

    return evaluate_portfolio_deterministic(db, portfolio_id)