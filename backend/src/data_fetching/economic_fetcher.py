import os
import pandas as pd
from datetime import datetime


def fetch_economic_data() -> pd.DataFrame:
    """
    Economic indicators for risk model.

    Week 2:
    Replace hardcoded values with RBI DBIE
    and eSankhyiki API integration.
    """

    records = [
        {
            "date": datetime.today().strftime("%Y-%m-%d"),
            "indicator": "Repo Rate",
            "value": 5.50,
            "source": "RBI DBIE"
        },
        {
            "date": datetime.today().strftime("%Y-%m-%d"),
            "indicator": "GDP Growth",
            "value": 6.80,
            "source": "eSankhyiki"
        },
        {
            "date": datetime.today().strftime("%Y-%m-%d"),
            "indicator": "Inflation",
            "value": 3.20,
            "source": "eSankhyiki"
        }
    ]

    return pd.DataFrame(records)


def save_economic_csv(df: pd.DataFrame):

    os.makedirs(
        "data/raw/economic",
        exist_ok=True
    )

    filepath = (
        "data/raw/economic/economic_indicators.csv"
    )

    df.to_csv(
        filepath,
        index=False
    )

    print(f"Saved -> {filepath}")


if __name__ == "__main__":

    df = fetch_economic_data()

    print(
        f"Economic Indicators: {len(df)} rows fetched"
    )

    save_economic_csv(df)