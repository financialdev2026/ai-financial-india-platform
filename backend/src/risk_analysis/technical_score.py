"""
=========================================================
Technical Score Engine
---------------------------------------------------------
Calculates:
    • RSI Score
    • MACD Score
    • Bollinger Band Score

Generates:
    • Technical Score
    • Technical Signal
    • Confidence
    • Reason

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
# Weights
# =========================================================

MACD_WEIGHT = 0.50
RSI_WEIGHT = 0.30
BOLLINGER_WEIGHT = 0.20

# =========================================================
# Load Data
# =========================================================


def load_data():

    technical = pd.read_sql(
        "SELECT * FROM technical_indicators",
        engine
    )

    stocks = pd.read_sql(
        """
        SELECT
            ticker,
            date,
            close
        FROM stocks
        """,
        engine
    )

    return technical, stocks


# =========================================================
# Clean Data
# =========================================================


def preprocess_data(
        technical,
        stocks
):

    technical["ticker"] = (
        technical["ticker"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    stocks["ticker"] = (
        stocks["ticker"]
        .astype(str)
        .str.strip()
        .str.upper()
    )

    technical["date"] = pd.to_datetime(
        technical["date"]
    )

    stocks["date"] = pd.to_datetime(
        stocks["date"]
    )

    return technical, stocks


# =========================================================
# Merge
# =========================================================


def merge_data(
        technical,
        stocks
):

    df = pd.merge(
        technical,
        stocks,
        on=[
            "ticker",
            "date"
        ],
        how="inner"
    )

    return df


# =========================================================
# RSI SCORE
# =========================================================


def calculate_rsi_score(
        rsi
):

    if pd.isna(rsi):
        return np.nan

    if rsi < 20:
        return 1.0

    elif rsi < 30:
        return 0.8

    elif rsi < 40:
        return 0.5

    elif rsi <= 60:
        return 0.0

    elif rsi <= 70:
        return -0.5

    elif rsi <= 80:
        return -0.8

    return -1.0


# =========================================================
# MACD SCORE
# =========================================================


def calculate_macd_score(
        macd,
        signal,
        histogram
):

    if (
        pd.isna(macd)
        or pd.isna(signal)
        or pd.isna(histogram)
    ):
        return np.nan

    # Strong Bullish

    if (
        macd > signal
        and histogram >= 1
    ):
        return 1.0

    # Bullish

    if (
        macd > signal
        and histogram > 0
    ):
        return 0.5

    # Strong Bearish

    if (
        macd < signal
        and histogram <= -1
    ):
        return -1.0

    # Bearish

    if (
        macd < signal
        and histogram < 0
    ):
        return -0.5

    return 0.0


# =========================================================
# Bollinger Score
# =========================================================


def calculate_bollinger_score(

        close,

        upper,

        middle,

        lower
):

    if (
        pd.isna(close)
        or pd.isna(upper)
        or pd.isna(middle)
        or pd.isna(lower)
    ):
        return np.nan

    if close <= lower:
        return 1.0

    if lower < close < middle:
        return 0.5

    if np.isclose(
        close,
        middle,
        atol=0.01
    ):
        return 0.0

    if middle < close < upper:
        return -0.5

    return -1.0


# =========================================================
# Calculate Indicator Scores
# =========================================================


def score_indicators(df):

    df["rsi_score"] = df["rsi"].apply(
        calculate_rsi_score
    )

    df["macd_score"] = df.apply(

        lambda row:

        calculate_macd_score(

            row["macd"],

            row["macd_signal"],

            row["macd_histogram"]

        ),

        axis=1

    )

    df["bollinger_score"] = df.apply(

        lambda row:

        calculate_bollinger_score(

            row["close"],

            row["bb_upper"],

            row["bb_middle"],

            row["bb_lower"]

        ),

        axis=1

    )

    return df
# =========================================================
# Technical Score
# =========================================================

def calculate_technical_score(df):

    df["technical_score"] = (
        MACD_WEIGHT * df["macd_score"] +
        RSI_WEIGHT * df["rsi_score"] +
        BOLLINGER_WEIGHT * df["bollinger_score"]
    )

    return df


# =========================================================
# Technical Signal
# =========================================================

def generate_signal(score):

    if pd.isna(score):
        return "UNKNOWN"

    if score >= 0.60:
        return "STRONGLY BULLISH"

    elif score >= 0.20:
        return "BULLISH"

    elif score > -0.20:
        return "CAUTIOUS"

    elif score > -0.60:
        return "BEARISH"

    return "STRONGLY BEARISH"


# =========================================================
# Confidence
# =========================================================

def calculate_confidence(row):

    scores = [
        row["macd_score"],
        row["rsi_score"],
        row["bollinger_score"]
    ]

    scores = [s for s in scores if not pd.isna(s)]

    if len(scores) == 0:
        return 0.0

    positive = sum(s > 0 for s in scores)
    negative = sum(s < 0 for s in scores)

    if positive == 3 or negative == 3:
        return 95.0

    if positive == 2 or negative == 2:
        return 80.0

    if positive == 1 and negative == 1:
        return 60.0

    return 50.0


# =========================================================
# Explainability
# =========================================================

def generate_reason(row):

    reasons = []

    # ---------- MACD ----------

    if row["macd_score"] >= 0.5:
        reasons.append("MACD Bullish")

    elif row["macd_score"] <= -0.5:
        reasons.append("MACD Bearish")

    # ---------- RSI ----------

    if row["rsi"] < 30:
        reasons.append("RSI Oversold")

    elif row["rsi"] > 70:
        reasons.append("RSI Overbought")

    # ---------- Bollinger ----------

    if row["bollinger_score"] == 1:
        reasons.append("Price Below Lower Bollinger Band")

    elif row["bollinger_score"] == -1:
        reasons.append("Price Above Upper Bollinger Band")

    elif row["bollinger_score"] == 0.5:
        reasons.append("Price Below Bollinger Mid Band")

    elif row["bollinger_score"] == -0.5:
        reasons.append("Price Above Bollinger Mid Band")

    if len(reasons) == 0:
        reasons.append("Indicators Neutral")

    return ", ".join(reasons)


# =========================================================
# Final Processing
# =========================================================

def process_scores(df):

    df = score_indicators(df)

    df = calculate_technical_score(df)

    df["signal"] = df["technical_score"].apply(
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
# Save
# =========================================================

def save_scores(df):

    output = df[
        [
            "ticker",
            "date",
            "macd_score",
            "rsi_score",
            "bollinger_score",
            "technical_score",
            "signal",
            "confidence",
            "reason"
        ]
    ]

    output.to_sql(
        "technical_scores",
        con=engine,
        if_exists="replace",
        index=False
    )

    print(f"\nSaved {len(output)} technical scores.")


# =========================================================
# Main
# =========================================================

def main():

    print("\n==============================")
    print(" Technical Score Engine")
    print("==============================")

    technical, stocks = load_data()

    technical, stocks = preprocess_data(
        technical,
        stocks
    )

    df = merge_data(
        technical,
        stocks
    )

    print(f"\nMerged Records : {len(df)}")

    df = process_scores(df)

    print("\nSample Results:\n")

    print(
        df[
            [
                "ticker",
                "technical_score",
                "signal",
                "confidence"
            ]
        ].head(10)
    )

    save_scores(df)

    print("\nTechnical Score Engine Completed.\n")


# =========================================================

if __name__ == "__main__":

    main()