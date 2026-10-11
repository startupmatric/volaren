import pandas as pd


def calculate_performance(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    # Current market value
    df["position_value"] = df["shares"] * df["current_price"]

    # Cost basis
    df["cost_basis"] = df["shares"] * df["avg_price"]

    # Profit / Loss (dollars)
    df["pnl"] = df["position_value"] - df["cost_basis"]

    # Return percentage for this position
    df["return_pct"] = (
        (df["current_price"] - df["avg_price"]) / df["avg_price"]
    ) * 100

    total_value = df["position_value"].sum()
    total_cost = df["cost_basis"].sum()

    # Portfolio weight (current-value based)
    df["weight_pct"] = (df["position_value"] / total_value) * 100

    # Contribution to portfolio return.
    # PnL / total_cost_basis * 100
    # Sum of contribution_pct == portfolio return_pct
    if total_cost > 0:
        df["contribution_pct"] = (df["pnl"] / total_cost) * 100
    else:
        df["contribution_pct"] = 0.0

    return df


def calculate_portfolio_metrics(df: pd.DataFrame) -> dict:
    total_value = df["position_value"].sum()
    total_cost = df["cost_basis"].sum()
    total_pnl = total_value - total_cost

    total_return_pct = (
        (total_pnl / total_cost) * 100 if total_cost != 0 else 0
    )

    return {
        "portfolio_value": round(float(total_value), 2),
        "cost_basis": round(float(total_cost), 2),
        "pnl": round(float(total_pnl), 2),
        "return_pct": round(float(total_return_pct), 2),
    }