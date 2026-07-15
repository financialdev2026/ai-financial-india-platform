"""
=========================================================
Volume Analysis Engine
---------------------------------------------------------
Calculates:

    • 20-Day Average Volume
    • Volume Ratio
    • Volume Score
    • Volume Signal

Output:

    volume_scores table

Author: ForSight AI
=========================================================
"""

import numpy as np
import pandas as pd

from sqlalchemy import create_engine

engine = create_engine(
    "sqlite:///data/financial_market.db"
)

# =========================================================
# Parameters
# =========================================================

ROLLING_WINDOW = 20

VERY_HIGH_VOLUME = 1.50
HIGH_VOLUME = 1.20

LOW_VOLUME = 0.80
VERY_LOW_VOLUME = 0.50

# =========================================================
# Load Stock Data
# =========================================================

def load_stock_data():

    query = """
        SELECT
            ticker,
            date,
            close,
            volume
        FROM stocks
    """

    df = pd.read_sql(
        query,
        engine
    )

    return df


# =========================================================
# Preprocessing
# =========================================================

def preprocess(df):

    df["ticker"] = (
        df["ticker"]
        .astype(str)
        .str.upper()
        .str.strip()
    )

    df["date"] = pd.to_datetime(
        df["date"]
    )

    df = df.sort_values(
        [
            "ticker",
            "date"
        ]
    )

    return df


# =========================================================
# Rolling Average Volume
# =========================================================

def calculate_average_volume(df):

    df["average_volume"] = (

        df.groupby("ticker")["volume"]

        .transform(

            lambda x:

            x.rolling(

                window=ROLLING_WINDOW,

                min_periods=ROLLING_WINDOW

            ).mean()

        )

    )

    return df


# =========================================================
# Volume Ratio
# =========================================================

def calculate_volume_ratio(df):

    df["volume_ratio"] = (

        df["volume"]

        /

        df["average_volume"]

    )

    return df


# =========================================================
# Score
# =========================================================

def calculate_volume_score(ratio):

    if pd.isna(ratio):
        return np.nan

    # Very High Volume

    if ratio >= VERY_HIGH_VOLUME:
        return 1.0

    # High Volume

    elif ratio >= HIGH_VOLUME:
        return 0.5

    # Normal Volume

    elif ratio >= LOW_VOLUME:
        return 0.0

    # Low Volume

    elif ratio >= VERY_LOW_VOLUME:
        return -0.5

    # Very Low Volume

    return -1.0


# =========================================================
# Signal
# =========================================================

def generate_signal(ratio):

    if pd.isna(ratio):
        return "UNKNOWN"

    if ratio >= VERY_HIGH_VOLUME:
        return "VERY HIGH"

    elif ratio >= HIGH_VOLUME:
        return "HIGH"

    elif ratio >= LOW_VOLUME:
        return "NORMAL"

    elif ratio >= VERY_LOW_VOLUME:
        return "LOW"

    return "VERY LOW"
# =========================================================
# Confidence
# =========================================================

def calculate_confidence(row):

    ratio = row["volume_ratio"]

    if pd.isna(ratio):
        return 0.0

    if ratio >= 2.0:
        return 95.0

    elif ratio >= 1.5:
        return 90.0

    elif ratio >= 1.2:
        return 80.0

    elif ratio >= 0.8:
        return 70.0

    elif ratio >= 0.5:
        return 80.0

    return 90.0


# =========================================================
# Explainability
# =========================================================

def generate_reason(row):

    ratio = row["volume_ratio"]

    if pd.isna(ratio):
        return "Insufficient historical volume data"

    if ratio >= 2.0:
        return "Extremely high trading volume"

    elif ratio >= 1.5:
        return "Very high trading volume"

    elif ratio >= 1.2:
        return "Above average trading volume"

    elif ratio >= 0.8:
        return "Normal trading volume"

    elif ratio >= 0.5:
        return "Below average trading volume"

    return "Extremely low trading volume"


# =========================================================
# Process Volume Analysis
# =========================================================

def process_volume_analysis(df):

    df = calculate_average_volume(df)

    df = calculate_volume_ratio(df)

    df["volume_score"] = df["volume_ratio"].apply(
        calculate_volume_score
    )

    df["signal"] = df["volume_ratio"].apply(
        generate_signal
    )

    df["confidence"] = df.apply(
        calculate_confidence,
        axis=1
    )

    df["reason"] = df.apply(
        generate_reason,
        axis=1
    )

    return df


# =========================================================
# Save Results
# =========================================================

def save_results(df):

    output = df[
        [
            "ticker",
            "date",
            "volume",
            "average_volume",
            "volume_ratio",
            "volume_score",
            "signal",
            "confidence",
            "reason"
        ]
    ]

    output = output.rename(
        columns={
            "volume": "current_volume"
        }
    )

    output.to_sql(
        "volume_scores",
        con=engine,
        if_exists="replace",
        index=False
    )

    print(f"\nSaved {len(output)} volume scores.")


# =========================================================
# Main
# =========================================================

def main():

    print("\n===============================")
    print(" Volume Analysis Engine")
    print("===============================\n")

    df = load_stock_data()

    df = preprocess(df)

    print(f"Loaded {len(df)} stock records.")

    df = process_volume_analysis(df)

    print("\nSample Results\n")

    print(

        df[
            [
                "ticker",
                "volume",
                "average_volume",
                "volume_ratio",
                "volume_score",
                "signal"
            ]
        ].tail(15)

    )

    save_results(df)

    print("\nVolume Analysis Completed.\n")


# =========================================================

if __name__ == "__main__":

    main()