import pandas as pd


def read_portfolio_csv(file_path: str):

    df = pd.read_csv(file_path)

    required_columns = [
        "ticker",
        "shares",
        "avg_price"
    ]

    for column in required_columns:

        if column not in df.columns:
            raise ValueError(
                f"Missing required column: {column}"
            )

    return df


def calculate_position_values(df):

    df = df.copy()

    df["position_value"] = (
        df["shares"] * df["avg_price"]
    )

    return df


def calculate_portfolio_value(df):

    return float(
        df["position_value"].sum()
    )
