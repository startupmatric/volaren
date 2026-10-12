"""
Pydantic schemas for evaluation responses.

These mirror the shape returned by evaluation_service.py.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class EvaluationScores(BaseModel):
    grounding: float
    ticker_accuracy: float
    fact_accuracy: float


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