"""
Evaluation harness.

Runs a set of golden cases through the agent, evaluates each
explanation, and returns an aggregate report.

Two modes:
  - real LLM  : pass a `agent_runner` that calls the real agent
  - mocked    : pass a `agent_runner` that returns a canned response

If no runner is provided, the harness assumes the caller has
already produced the explanation and only does evaluation.
"""

from typing import Any, Callable, Optional

from app.evaluation.datasets import GOLDEN_CASES, get_case_by_name
from app.evaluation.evaluator import evaluate_explanation


# Signature of an agent runner:
#   runner(case: dict) -> str (the explanation text)
AgentRunner = Callable[[dict], str]


# =========================================================
# SINGLE CASE
# =========================================================

def run_single_case(
    case: dict,
    agent_runner: AgentRunner,
) -> dict:
    """
    Run one golden case:
      1. ask the agent_runner to produce an explanation
      2. evaluate that explanation against the case

    Returns an evaluation report plus the raw explanation.
    """

    case_name = case.get("name", "<unnamed>")

    try:
        explanation = agent_runner(case)

    except Exception as exc:
        return {
            "case_name": case_name,
            "passed": False,
            "error": f"{exc.__class__.__name__}: {exc}",
            "explanation": "",
            "scores": {
                "grounding": 0.0,
                "ticker_accuracy": 0.0,
                "fact_accuracy": 0.0,
            },
        }

    report = evaluate_explanation(explanation, case)

    return {
        **report,
        "explanation": explanation,
    }


# =========================================================
# FULL SUITE
# =========================================================

def run_all_cases(
    agent_runner: AgentRunner,
    cases: Optional[list] = None,
) -> dict:
    """
    Run the full golden dataset.

    Args:
        agent_runner: callable that takes a case dict and returns
                      the explanation text
        cases:        optionally a subset of cases; defaults to
                      all GOLDEN_CASES

    Returns:
        {
            "total":       int,
            "passed":      int,
            "failed":      int,
            "pass_rate":   float (0..1),
            "results":     [list of per-case reports],
        }
    """

    cases = cases if cases is not None else GOLDEN_CASES

    results = []

    for case in cases:
        result = run_single_case(case, agent_runner)
        results.append(result)

    total = len(results)
    passed = sum(1 for r in results if r.get("passed"))
    failed = total - passed
    pass_rate = round(passed / total, 4) if total else 0.0

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "pass_rate": pass_rate,
        "results": results,
    }


# =========================================================
# AGGREGATE METRICS
# =========================================================

def summarize(report: dict) -> dict:
    """
    Compute average scores across all cases.

    Useful for logging / dashboards.
    """

    results = report.get("results") or []

    if not results:
        return {
            "avg_grounding": 0.0,
            "avg_ticker_accuracy": 0.0,
            "avg_fact_accuracy": 0.0,
        }

    def avg(key: str) -> float:
        values = [
            float((r.get("scores") or {}).get(key, 0.0))
            for r in results
        ]
        return round(sum(values) / len(values), 4) if values else 0.0

    return {
        "avg_grounding": avg("grounding"),
        "avg_ticker_accuracy": avg("ticker_accuracy"),
        "avg_fact_accuracy": avg("fact_accuracy"),
    }


# =========================================================
# SINGLE CASE LOOKUP
# =========================================================

def run_case_by_name(
    name: str,
    agent_runner: AgentRunner,
) -> Optional[dict]:
    """Run a single golden case by name."""
    case = get_case_by_name(name)
    if case is None:
        return None
    return run_single_case(case, agent_runner)