from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


# ---------- Holding-level ----------

class HoldingResponse(BaseModel):
    ticker: str
    shares: float
    avg_price: float
    current_price: float
    sector: Optional[str] = None

    position_value: float
    cost_basis: float
    pnl: float
    return_pct: float
    weight_pct: float
    contribution_pct: float


# ---------- Snapshot-level ----------

class PortfolioMetrics(BaseModel):
    portfolio_value: float
    cost_basis: float
    pnl: float
    return_pct: float


class SnapshotResponse(BaseModel):
    id: int
    portfolio_id: int
    created_at: datetime

    portfolio_value: float
    cost_basis: float
    pnl: float
    return_pct: float

    holdings: List[HoldingResponse] = []


# ---------- Upload response (Day 2 shape, now with ids) ----------

class UploadResponse(BaseModel):
    portfolio_id: int
    snapshot_id: int
    portfolio: PortfolioMetrics
    holdings: List[HoldingResponse]


# ---------- Portfolio list ----------

class PortfolioSummary(BaseModel):
    id: int
    name: str
    created_at: datetime
    snapshot_count: int
    latest_snapshot_id: Optional[int] = None
    latest_portfolio_value: Optional[float] = None
    latest_return_pct: Optional[float] = None


class PortfolioListResponse(BaseModel):
    portfolios: List[PortfolioSummary]


# ---------- What Changed (diff) ----------

class WeightChange(BaseModel):
    ticker: str
    weight_before_pct: float
    weight_after_pct: float
    weight_delta_pct: float


class ContributionChange(BaseModel):
    ticker: str
    contribution_before_pct: float
    contribution_after_pct: float
    contribution_delta_pct: float


class DiffResponse(BaseModel):
    portfolio_id: int
    previous_snapshot_id: Optional[int] = None
    latest_snapshot_id: int

    previous_created_at: Optional[datetime] = None
    latest_created_at: datetime

    portfolio_value_before: Optional[float] = None
    portfolio_value_after: float
    portfolio_value_delta: Optional[float] = None

    return_pct_before: Optional[float] = None
    return_pct_after: float
    return_pct_delta: Optional[float] = None

    weight_changes: List[WeightChange] = []
    contribution_changes: List[ContributionChange] = []

    new_positions: List[str] = []
    closed_positions: List[str] = []