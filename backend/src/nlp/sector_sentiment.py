import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(
    "sqlite:///data/financial_market.db"
)


def calculate_sector_sentiment():

    df = pd.read_sql(
        "SELECT * FROM news_sentiment",
        engine
    )

    sentiment_score = {
        "positive": 1,
        "neutral": 0,
        "negative": -1
    }

    df["score"] = (
        df["sentiment"]
        .map(sentiment_score)
    )

    sector_summary = (

        df.groupby("sector")

        .agg({

            "score": "mean",

            "sentiment": "count"
        })

        .reset_index()

    )

    sector_summary.columns = [
        "sector",
        "avg_sentiment_score",
        "article_count"
    ]

    return sector_summary


if __name__ == "__main__":

    result = calculate_sector_sentiment()

    print("\nSector Sentiment:\n")

    print(result)