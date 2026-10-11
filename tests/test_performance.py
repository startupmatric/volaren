import pandas as pd

from app.services.performance_service import (
    calculate_performance,
    calculate_portfolio_metrics,
)


def test_performance_calculation():
    df = pd.DataFrame([
        {
            "ticker": "NVDA",
            "shares": 20,
            "avg_price": 165,
            "current_price": 180,
            "sector": "Semiconductors",
        }
    ])

    result = calculate_performance(df)

    assert result.iloc[0]["position_value"] == 3600
    assert result.iloc[0]["cost_basis"] == 3300
    assert result.iloc[0]["pnl"] == 300


def test_portfolio_metrics():
    df = pd.DataFrame([
        {
            "ticker": "NVDA",
            "shares": 20,
            "avg_price": 165,
            "current_price": 180,
            "sector": "Semiconductors",
        }
    ])

    df = calculate_performance(df)
    metrics = calculate_portfolio_metrics(df)

    assert metrics["portfolio_value"] == 3600
    assert metrics["cost_basis"] == 3300
    assert metrics["pnl"] == 300