"""
FII / DII score engine.

Scores all institutional rows for auditability, while clearly marking the
latest available trading date for downstream current-market calculations.
"""

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

from src.utils.freshness import parse_datetime


engine = create_engine("sqlite:///data/financial_market.db")


def load_data():
    return pd.read_sql("SELECT * FROM fii_dii", engine)


def calculate_flow_score(net):
    if pd.isna(net):
        return np.nan
    if net >= 5000:
        return 1.0
    if net >= 2000:
        return 0.5
    if net > -2000:
        return 0.0
    if net > -5000:
        return -0.5
    return -1.0


def generate_signal(score):
    if pd.isna(score):
        return "UNKNOWN"
    if score == 1:
        return "VERY BULLISH"
    if score == 0.5:
        return "BULLISH"
    if score == 0:
        return "NEUTRAL"
    if score == -0.5:
        return "BEARISH"
    return "VERY BEARISH"


def calculate_confidence(row):
    net = abs(row["net_value"])
    if pd.isna(net):
        return 0.0
    if net >= 10000:
        return 95.0
    if net >= 5000:
        return 90.0
    if net >= 3000:
        return 80.0
    if net >= 1000:
        return 70.0
    return 60.0


def generate_reason(row):
    net = row["net_value"]
    scope = "latest trading date" if row.get("is_latest_date") else "historical date"

    if pd.isna(net):
        return f"Institutional flow unavailable for this {scope}"
    if net >= 5000:
        return f"Heavy institutional buying on the {scope}"
    if net >= 2000:
        return f"Strong institutional buying on the {scope}"
    if net > -2000:
        return f"Balanced institutional activity on the {scope}"
    if net > -5000:
        return f"Moderate institutional selling on the {scope}"
    return f"Heavy institutional selling on the {scope}"


def process(df):
    output = df.copy()
    output["_parsed_date"] = parse_datetime(output["date"])
    output = (
        output.sort_values("_parsed_date")
        .drop_duplicates(["date", "client_type"], keep="last")
        .copy()
    )
    latest_date = output["_parsed_date"].max()
    output["is_latest_date"] = output["_parsed_date"] == latest_date
    output["flow_score"] = output["net_value"].apply(calculate_flow_score)
    output["signal"] = output["flow_score"].apply(generate_signal)
    output["confidence"] = output.apply(calculate_confidence, axis=1)
    output["reason"] = output.apply(generate_reason, axis=1)
    return output.sort_values(["_parsed_date", "client_type"])


def save_results(df):
    output = df[
        [
            "date",
            "client_type",
            "buy_value",
            "sell_value",
            "net_value",
            "flow_score",
            "signal",
            "confidence",
            "reason",
            "is_latest_date",
        ]
    ]

    output.to_sql("fii_dii_scores", con=engine, if_exists="replace", index=False)
    latest_count = int(output["is_latest_date"].sum())
    print(f"\nSaved {len(output)} FII/DII scores ({latest_count} current rows).")


def main():
    print("\n===============================")
    print(" FII / DII Score Engine")
    print("===============================\n")

    df = process(load_data())

    print("\nLatest Institutional Flow\n")
    print(
        df[df["is_latest_date"]][
            ["client_type", "net_value", "flow_score", "signal", "confidence"]
        ]
    )

    save_results(df)
    print("\nFII/DII Score Engine Completed.\n")


if __name__ == "__main__":
    main()
