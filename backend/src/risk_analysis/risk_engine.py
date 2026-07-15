"""
FORESIGHT AI Risk Engine.

The engine builds a current market snapshot instead of allowing old rows or a
single ticker's final database row to dominate the recommendation.
"""

import pandas as pd
from sqlalchemy import create_engine

from src.utils.freshness import bounded_mean, latest_per_group, latest_rows, iso_date


engine = create_engine("sqlite:///data/financial_market.db")

TECHNICAL_WEIGHT = 0.40
NEWS_WEIGHT = 0.25
VOLUME_WEIGHT = 0.15
ECONOMIC_WEIGHT = 0.10
FII_WEIGHT = 0.10


def load_scores():
    return {
        "technical": pd.read_sql("SELECT * FROM technical_scores", engine),
        "volume": pd.read_sql("SELECT * FROM volume_scores", engine),
        "economic": pd.read_sql("SELECT * FROM economic_scores", engine),
        "fii": pd.read_sql("SELECT * FROM fii_dii_scores", engine),
        "news": pd.read_sql("SELECT * FROM news_scores", engine),
    }


def technical_snapshot(df):
    latest = latest_per_group(
        df,
        group_column="ticker",
        required_columns=["technical_score"],
    )
    return {
        "score": bounded_mean(latest["technical_score"]),
        "rows": len(latest),
        "date": iso_date(latest["_parsed_date"].max()) if not latest.empty else "",
    }


def volume_snapshot(df):
    latest = latest_per_group(
        df,
        group_column="ticker",
        required_columns=["volume_score"],
    )
    return {
        "score": bounded_mean(latest["volume_score"]),
        "rows": len(latest),
        "date": iso_date(latest["_parsed_date"].max()) if not latest.empty else "",
    }


def latest_scalar_snapshot(df, score_column):
    latest = latest_rows(df)
    return {
        "score": bounded_mean(latest[score_column]) if score_column in latest.columns else 0.0,
        "rows": len(latest),
        "date": iso_date(latest["_parsed_date"].max()) if not latest.empty else "",
    }


def news_snapshot(df):
    if df.empty:
        return {"score": 0.0, "rows": 0, "date": ""}

    score = bounded_mean(df["news_score"])
    latest_at = ""
    if "latest_article_at" in df.columns:
        latest_at = iso_date(pd.to_datetime(df["latest_article_at"], errors="coerce").max())

    return {
        "score": score,
        "rows": len(df),
        "date": latest_at,
    }


def combine_scores(tables):
    technical = technical_snapshot(tables["technical"])
    volume = volume_snapshot(tables["volume"])
    economic = latest_scalar_snapshot(tables["economic"], "economic_score")
    fii_table = tables["fii"].drop_duplicates(["date", "client_type"], keep="last")
    fii = latest_scalar_snapshot(fii_table, "flow_score")
    news = news_snapshot(tables["news"])

    final_score = (
        TECHNICAL_WEIGHT * technical["score"]
        + NEWS_WEIGHT * news["score"]
        + VOLUME_WEIGHT * volume["score"]
        + ECONOMIC_WEIGHT * economic["score"]
        + FII_WEIGHT * fii["score"]
    )

    return {
        "technical": technical["score"],
        "news": news["score"],
        "volume": volume["score"],
        "economic": economic["score"],
        "fii": fii["score"],
        "final": final_score,
        "metadata": {
            "technical_rows": technical["rows"],
            "volume_rows": volume["rows"],
            "news_rows": news["rows"],
            "economic_rows": economic["rows"],
            "fii_rows": fii["rows"],
            "technical_date": technical["date"],
            "volume_date": volume["date"],
            "news_date": news["date"],
            "economic_date": economic["date"],
            "fii_date": fii["date"],
        },
    }


def generate_signal(score):
    if score >= 0.60:
        return "STRONGLY BULLISH"
    if score >= 0.20:
        return "BULLISH"
    if score > -0.20:
        return "CAUTIOUS"
    if score > -0.60:
        return "BEARISH"
    return "STRONGLY BEARISH"


def calculate_agreement(scores):
    positive = sum(score > 0.20 for score in scores)
    negative = sum(score < -0.20 for score in scores)
    neutral = len(scores) - positive - negative
    return round(max(positive, negative, neutral) / len(scores) * 100, 2)


def calculate_confidence(final_score, agreement, metadata):
    coverage_factor = min(
        1.0,
        (
            min(metadata["technical_rows"], 10) / 10
            + min(metadata["volume_rows"], 10) / 10
            + min(metadata["news_rows"], 5) / 5
            + min(metadata["economic_rows"], 1)
            + min(metadata["fii_rows"], 2) / 2
        )
        / 5,
    )
    confidence = (abs(final_score) * 45 + agreement * 0.45 + coverage_factor * 20)
    return round(min(confidence, 100), 2)


def generate_reason(scores):
    reasons = []

    if scores["technical"] > 0.20:
        reasons.append("latest technical snapshot is bullish")
    elif scores["technical"] < -0.20:
        reasons.append("latest technical snapshot is bearish")

    if scores["news"] > 0.20:
        reasons.append("recent news sentiment is positive")
    elif scores["news"] < -0.20:
        reasons.append("recent news sentiment is negative")

    if scores["volume"] > 0.20:
        reasons.append("current volume confirms participation")
    elif scores["volume"] < -0.20:
        reasons.append("current volume participation is weak")

    if scores["economic"] > 0.20:
        reasons.append("macro indicators are supportive")
    elif scores["economic"] < -0.20:
        reasons.append("macro indicators are weak")

    if scores["fii"] > 0.20:
        reasons.append("latest institutional flow is positive")
    elif scores["fii"] < -0.20:
        reasons.append("latest institutional flow is negative")

    return ", ".join(reasons) if reasons else "mixed current market signals"


def save_results(scores):
    module_scores = [
        scores["technical"],
        scores["news"],
        scores["volume"],
        scores["economic"],
        scores["fii"],
    ]
    agreement = calculate_agreement(module_scores)
    confidence = calculate_confidence(scores["final"], agreement, scores["metadata"])
    signal = generate_signal(scores["final"])
    reason = generate_reason(scores)
    metadata = scores["metadata"]

    output = pd.DataFrame(
        [
            {
                "date": pd.Timestamp.now().strftime("%Y-%m-%d"),
                "technical_score": round(scores["technical"], 4),
                "news_score": round(scores["news"], 4),
                "volume_score": round(scores["volume"], 4),
                "economic_score": round(scores["economic"], 4),
                "fii_score": round(scores["fii"], 4),
                "final_score": round(scores["final"], 4),
                "signal": signal,
                "confidence": confidence,
                "agreement_score": agreement,
                "reason": reason,
                **metadata,
            }
        ]
    )

    output.to_sql("risk_scores", con=engine, if_exists="replace", index=False)

    print("\n========== FINAL AI RECOMMENDATION ==========\n")
    print(output.to_string(index=False))
    print("\n=============================================\n")


def main():
    print("\n========================================")
    print(" FORESIGHT AI RISK ENGINE")
    print("========================================\n")

    scores = combine_scores(load_scores())
    save_results(scores)

    print("\nRisk Engine Completed.\n")


if __name__ == "__main__":
    main()
