"""
Pydantic schemas for evaluation and agent responses.

These mirror the shape returned by evaluation_service.py and
agents/portfolio_agent.py.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class EvaluationScores(BaseModel):
    grounding: float
    ticker_accuracy: float
    fact_accuracy: float


class ToolCallRecord(BaseModel):
    name: str
    args: Dict[str, Any] = {}
    latency_ms: Optional[float] = None


class ToolCoverage(BaseModel):
    intent: Optional[str] = None
    required: List[str] = []
    called: List[str] = []
    missing: List[str] = []
    satisfied: bool = True
    coverage: float = 1.0


class EvaluationReport(BaseModel):
    portfolio_id: int
    snapshot_id: Optional[int] = None
    source: str
    latency_ms: float
    passed: bool
    scores: EvaluationScores
    unsupported_numbers: List[float] = []
    unsupported_tickers: List[str] = []
    missing_expected_facts: Dict[str, Any] = {}
    found_expected_facts: Dict[str, Any] = {}
    explanation: str = ""
    tool_calls: List[ToolCallRecord] = []
    tool_coverage: ToolCoverage = ToolCoverage()


# =========================================================
# TOOL-CALLING AGENT RESPONSE (Day 8a)
# =========================================================

class AgentExplainResponse(BaseModel):
    portfolio_id: int
    explanation: str
    source: str
    validation: Dict[str, Any] = {}
    tool_calls: List[ToolCallRecord] = []