"""
Wrapper around the LangGraph portfolio agent.

The agent service is called from the API layer. This module:
  - runs the graph
  - handles the "no snapshots" case
  - ensures a response is always returned, even if the graph crashes
"""

from typing import Optional

from sqlalchemy.orm import Session

from app.agents.portfolio_agent import run_agent


def explain_portfolio_with_agent(
    db: Session,
    portfolio_id: int,
) -> Optional[dict]:
    """
    Run the LangGraph agent and return the final explanation dict.

    Returns None if the portfolio has no snapshots.
    """

    try:
        return run_agent(db, portfolio_id)

    except Exception as exc:
        # Any unhandled exception becomes a served response with
        # source="error". The API layer will map this to 500.
        return {
            "portfolio_id": portfolio_id,
            "explanation": "",
            "source": "error",
            "validation": {
                "valid": False,
                "unknown": [],
                "error": f"{exc.__class__.__name__}: {exc}",
            },
        }