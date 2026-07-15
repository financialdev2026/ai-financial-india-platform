"""
=========================================================
Economic Score Engine

Calculates

• Repo Rate Score
• GDP Score
• Inflation Score

Output

economic_scores

=========================================================
"""

import numpy as np
import pandas as pd

from sqlalchemy import create_engine

engine = create_engine(
    "sqlite:///data/financial_market.db"
)
# =======================================================
# Weights
# =======================================================

REPO_WEIGHT = 0.40

GDP_WEIGHT = 0.35

INFLATION_WEIGHT = 0.25

# =======================================================
# Load
# =======================================================

def load_data():

    query = """
    SELECT *
    FROM economic_data
    """

    return pd.read_sql(
        query,
        engine
    )

# =======================================================
# Pivot
# =======================================================

def preprocess(df):

    df = df.pivot_table(

        index="date",

        columns="indicator",

        values="value",

        aggfunc="last"

    ).reset_index()

    df.columns.name = None

    return df

# =======================================================
# Repo Score
# =======================================================

def calculate_repo_score(repo):

    if pd.isna(repo):
        return np.nan

    if repo <= 5:
        return 1.0

    elif repo <= 6:

        return 0.5

    elif repo <= 7:

        return 0.0

    elif repo <= 8:

        return -0.5

    return -1.0

# =======================================================
# GDP Score
# =======================================================

def calculate_gdp_score(gdp):

    if pd.isna(gdp):
        return np.nan

    if gdp >= 8:

        return 1.0

    elif gdp >= 7:

        return 0.5

    elif gdp >= 6:

        return 0.0

    elif gdp >= 5:

        return -0.5

    return -1.0

# =======================================================
# Inflation Score
# =======================================================

def calculate_inflation_score(inflation):

    if pd.isna(inflation):
        return np.nan

    if inflation <= 3:

        return 1.0

    elif inflation <= 5:

        return 0.5

    elif inflation <= 6:

        return 0.0

    elif inflation <= 7:

        return -0.5

    return -1.0

# =======================================================
# Indicator Scores
# =======================================================

def score_indicators(df):

    df["repo_score"] = df["Repo Rate"].apply(
        calculate_repo_score
    )

    df["gdp_score"] = df["GDP Growth"].apply(
        calculate_gdp_score
    )

    df["inflation_score"] = df["Inflation"].apply(
        calculate_inflation_score
    )

    return df
# =======================================================
# Economic Score
# =======================================================

def calculate_economic_score(df):

    df["economic_score"] = (

        REPO_WEIGHT * df["repo_score"]

        +

        GDP_WEIGHT * df["gdp_score"]

        +

        INFLATION_WEIGHT * df["inflation_score"]

    )

    return df


# =======================================================
# Signal
# =======================================================

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


# =======================================================
# Confidence
# =======================================================

def calculate_confidence(row):

    scores = [

        row["repo_score"],

        row["gdp_score"],

        row["inflation_score"]

    ]

    scores = [

        s for s in scores

        if not pd.isna(s)

    ]

    if len(scores) == 0:
        return 0.0

    positive = sum(s > 0 for s in scores)

    negative = sum(s < 0 for s in scores)

    if positive == 3 or negative == 3:
        return 95.0

    elif positive == 2 or negative == 2:
        return 80.0

    elif positive == 1 and negative == 1:
        return 60.0

    return 50.0


# =======================================================
# Explainability
# =======================================================

def generate_reason(row):

    reasons = []

    if row["repo_score"] > 0:
        reasons.append("Favourable Repo Rate")

    elif row["repo_score"] < 0:
        reasons.append("High Repo Rate")

    if row["gdp_score"] > 0:
        reasons.append("Strong GDP Growth")

    elif row["gdp_score"] < 0:
        reasons.append("Weak GDP Growth")

    if row["inflation_score"] > 0:
        reasons.append("Controlled Inflation")

    elif row["inflation_score"] < 0:
        reasons.append("High Inflation")

    if len(reasons) == 0:
        reasons.append("Neutral Economic Indicators")

    return ", ".join(reasons)


# =======================================================
# Processing
# =======================================================

def process(df):

    df = score_indicators(df)

    df = calculate_economic_score(df)

    df["signal"] = df["economic_score"].apply(
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


# =======================================================
# Save
# =======================================================

def save_results(df):

    output = df[
        [
            "date",

            "Repo Rate",
            "GDP Growth",
            "Inflation",

            "repo_score",
            "gdp_score",
            "inflation_score",

            "economic_score",

            "signal",

            "confidence",

            "reason"
        ]
    ]

    output = output.rename(
        columns={
            "Repo Rate": "repo_rate",
            "GDP Growth": "gdp_growth",
            "Inflation": "inflation"
        }
    )

    output.to_sql(
        "economic_scores",
        con=engine,
        if_exists="replace",
        index=False
    )

    print(
        f"\nSaved {len(output)} economic scores."
    )


# =======================================================
# Main
# =======================================================

def main():

    print("\n===============================")
    print(" Economic Score Engine")
    print("===============================\n")

    df = load_data()

    df = preprocess(df)

    df = process(df)

    print("\nSample Results\n")

    print(
        df[
            [
                "economic_score",
                "signal",
                "confidence"
            ]
        ]
    )

    save_results(df)

    print("\nEconomic Score Engine Completed.\n")


# =======================================================

if __name__ == "__main__":

    main()