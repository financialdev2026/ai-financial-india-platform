"""
Recency-aware news score engine.

Only recent articles should drive current market sentiment. Older articles are
kept in the database for history, but their influence decays before sector
scores are written to news_scores.
"""

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

from src.utils.freshness import parse_datetime, recency_weight, weighted_average


engine = create_engine("sqlite:///data/financial_market.db")
NEWS_WINDOW_DAYS = 7
NEWS_HALF_LIFE_DAYS = 3

EXPECTED_SECTORS = ["IT", "BANK", "AUTO", "PHARMA", "FMCG"]


def load_data():
    query = """
        SELECT
            sector,
            sentiment,
            confidence,
            published_at
        FROM news_sentiment
    """
    return pd.read_sql(query, engine)


def sentiment_value(sentiment, confidence):
    if pd.isna(sentiment):
        return 0.0

    sentiment = str(sentiment).lower()
    if sentiment == "positive":
        return float(confidence)
    if sentiment == "negative":
        return -float(confidence)
    return 0.0


def apply_freshness_window(df):
    output = df.copy()
    output["_published_at"] = parse_datetime(output["published_at"])
    latest = output["_published_at"].max()

    if pd.isna(latest):
        return output.tail(120).copy()

    cutoff = latest - pd.Timedelta(days=NEWS_WINDOW_DAYS)
    current = output[output["_published_at"] >= cutoff].copy()

    if current.empty:
        current = output.sort_values("_published_at").tail(120).copy()

    current["_age_days"] = (
        latest - current["_published_at"]
    ).dt.total_seconds() / 86400
    current["_recency_weight"] = current["_age_days"].apply(
        lambda age: recency_weight(age, NEWS_HALF_LIFE_DAYS)
    )
    current["_sentiment_value"] = current.apply(
        lambda row: sentiment_value(row["sentiment"], row["confidence"]),
        axis=1,
    )
    current["_weighted_value"] = (
        current["_sentiment_value"] * current["_recency_weight"]
    )
    return current


def aggregate_sector_scores(df):
    grouped = (
        df.groupby("sector")
        .agg(
            positive_articles=("sentiment", lambda x: (x == "positive").sum()),
            neutral_articles=("sentiment", lambda x: (x == "neutral").sum()),
            negative_articles=("sentiment", lambda x: (x == "negative").sum()),
            average_confidence=("confidence", "mean"),
            recency_weight=("_recency_weight", "sum"),
            latest_article_at=("_published_at", "max"),
            article_window_start=("_published_at", "min"),
            article_count=("sentiment", "count"),
        )
        .reset_index()
    )

    weighted = []
    for sector in grouped["sector"]:
        sector_rows = df[df["sector"] == sector]
        weighted.append(
            weighted_average(
                sector_rows["_sentiment_value"],
                sector_rows["_recency_weight"],
            )
        )

    grouped["weighted_sentiment"] = weighted
    return grouped


def calculate_news_score(row):
    weight = row["weighted_sentiment"]
    articles = max(float(row.get("article_count", 0) or 0), 0.0)

    if pd.isna(weight) or articles == 0:
        return np.nan

    recency = min(float(row.get("recency_weight", 0) or 0) / max(articles, 1.0), 1.0)
    evidence = min(np.log1p(articles) / np.log1p(12), 1.0)

    sample_adjustment = 0.70 + (0.30 * evidence)
    recency_adjustment = 0.85 + (0.15 * recency)
    score = float(weight) * sample_adjustment * recency_adjustment
    return round(float(np.clip(score, -1.0, 1.0)), 4)


def generate_signal(score):
    if pd.isna(score):
        return "UNKNOWN"
    if score >= 0.65:
        return "VERY BULLISH"
    if score >= 0.20:
        return "BULLISH"
    if score > -0.20:
        return "NEUTRAL"
    if score > -0.65:
        return "BEARISH"
    return "VERY BEARISH"


def calculate_confidence(row):
    articles = row["article_count"]
    avg_conf = row["average_confidence"]
    recency = min(row["recency_weight"] / max(articles, 1), 1.0)

    if articles == 0 or pd.isna(avg_conf):
        return 0.0

    confidence = min(articles / 12, 1.0) * avg_conf * 100 * (0.70 + 0.30 * recency)
    return round(float(confidence), 2)


def generate_reason(row):
    age = ""
    if not pd.isna(row["latest_article_at"]):
        latest = pd.Timestamp(row["latest_article_at"]).strftime("%Y-%m-%d")
        age = f" Latest article: {latest}."

    articles = int(row.get("article_count", 0) or 0)
    if articles == 0:
        return f"No recent sector-specific news found.{age}"

    if row["news_score"] >= 0.5:
        return (
            f"Recent sector news is predominantly positive "
            f"({row['positive_articles']} positive articles).{age}"
        )
    if row["news_score"] <= -0.5:
        return (
            f"Recent sector news is predominantly negative "
            f"({row['negative_articles']} negative articles).{age}"
        )
    return f"Recent sector news is mixed or neutral.{age}"


def process(df):
    current = apply_freshness_window(df)
    grouped = aggregate_sector_scores(current)

    grouped["news_score"] = grouped.apply(calculate_news_score, axis=1)
    grouped["signal"] = grouped["news_score"].apply(generate_signal)
    grouped["confidence"] = grouped.apply(calculate_confidence, axis=1)
    grouped["reason"] = grouped.apply(generate_reason, axis=1)
    grouped["freshness_days"] = (
        pd.to_datetime(grouped["latest_article_at"]).max()
        - pd.to_datetime(grouped["latest_article_at"])
    ).dt.total_seconds().div(86400).round(2)

    for sector in EXPECTED_SECTORS:
        if sector not in grouped["sector"].values:
            missing = pd.DataFrame([{
                "sector": sector,
                "positive_articles": 0,
                "neutral_articles": 0,
                "negative_articles": 0,
                "average_confidence": 0.0,
                "weighted_sentiment": 0.0,
                "news_score": np.nan,
                "signal": "UNKNOWN",
                "confidence": 0.0,
                "reason": "No recent sector-specific news articles available.",
                "sector_rank": len(grouped) + 1,
                "article_count": 0,
                "latest_article_at": "",
                "article_window_start": "",
                "freshness_days": np.nan,
            }])
            grouped = pd.concat([grouped, missing], ignore_index=True)

    return grouped


def rank_sectors(df):
    output = df.copy()
    output["_sort_score"] = output["news_score"].fillna(-999)
    output = output.sort_values(
        by=["_sort_score", "confidence", "article_count"],
        ascending=[False, False, False],
    ).copy()
    output["sector_rank"] = range(1, len(output) + 1)
    output = output.drop(columns=["_sort_score"])
    return output


def save_results(df):
    output = df[
        [
            "sector",
            "positive_articles",
            "neutral_articles",
            "negative_articles",
            "average_confidence",
            "weighted_sentiment",
            "news_score",
            "signal",
            "confidence",
            "reason",
            "sector_rank",
            "article_count",
            "latest_article_at",
            "article_window_start",
            "freshness_days",
        ]
    ].copy()

    output["latest_article_at"] = output["latest_article_at"].astype(str)
    output["article_window_start"] = output["article_window_start"].astype(str)

    output.to_sql("news_scores", con=engine, if_exists="replace", index=False)
    print(f"\nSaved {len(output)} current-window news scores.")


def main():
    print("\n====================================")
    print(" Recency-Aware News Score Engine")
    print("====================================\n")

    df = load_data()
    df = process(df)
    df = rank_sectors(df)

    print("\nSector Rankings\n")
    print(df[["sector", "sector_rank", "news_score", "signal", "confidence"]])

    save_results(df)
    print("\nNews Score Engine Completed.\n")


if __name__ == "__main__":
    main()
