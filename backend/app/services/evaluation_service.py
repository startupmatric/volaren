"""
Evaluation service.

Runs the agent (deterministic OR LLM) on a real portfolio and
evaluates the resulting explanation against the actual evidence.

This is the glue between:
  - agents/tools.py  (evidence gathering)
  - agents/portfolio_agent.py  (LLM reasoning)
  - services/explain_service.py  (deterministic text)
  - evaluation/evaluator.py  (scoring)

The report shape is stable — the API wraps it directly.
"""

import time
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.agents.tools import gather_evidence
from app.evaluation.evaluator import evaluate_explanation
from app.services.agent_explain_service import (
    explain_portfolio_with_agent,
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
    )


# =========================================================
# AGENT MODE
# =========================================================

def evaluate_portfolio_with_agent(
    db: Session,
    portfolio_id: int,
) -> Optional[dict]:
    """
    Evaluate the *LLM* explanation for a real portfolio.

    Falls back gracefully when the LLM is unavailable.
    Reports the fallback source in the response.

    Returns None if the portfolio has no snapshots.
    """

    evidence = gather_evidence(db, portfolio_id)

    if evidence is None:
        return None

    started_at = time.perf_counter()

    agent_result = explain_portfolio_with_agent(db, portfolio_id)

    if agent_result is None:
        return None

    explanation = agent_result.get("explanation", "")
    source = agent_result.get("source", "unknown")

    case = _build_case_from_evidence(evidence, explanation)

    evaluation = evaluate_explanation(explanation, case)

    # If the LLM failed and we fell back, this is a soft failure.
    # We still report scores but mark the source clearly.
    if source == "deterministic_fallback":
        evaluation["passed"] = False
        evaluation.setdefault("reason", "llm_fallback")

    elapsed_ms = (time.perf_counter() - started_at) * 1000

    return _build_report(
        portfolio_id=portfolio_id,
        snapshot_id=evidence.get("snapshot_id"),
        source=source,
        explanation=explanation,
        evaluation=evaluation,
        latency_ms=elapsed_ms,
    )


# =========================================================
# UNIFIED ENTRY POINT
# =========================================================

def evaluate_portfolio(
    db: Session,
    portfolio_id: int,
    mode: str = "deterministic",
) -> Optional[dict]:
    """
    Unified entry point.

    mode = "deterministic" | "agent"
    """

    if mode == "agent":
        return evaluate_portfolio_with_agent(db, portfolio_id)

    return evaluate_portfolio_deterministic(db, portfolio_id)