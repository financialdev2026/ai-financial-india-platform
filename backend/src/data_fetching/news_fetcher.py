import os
import requests
import pandas as pd
from dotenv import load_dotenv
from pathlib import Path

MARKETAUX_URL = "https://api.marketaux.com/v1/news/all"

NEWS_COLUMNS = [
    "title",
    "description",
    "source",
    "published_at",
    "url"
]


def fetch_financial_news(
    api_key: str,
    countries: str = "in",
    language: str = "en",
    limit: int = 50
) -> pd.DataFrame:
    """
    Fetch Indian financial news from Marketaux.
    """

    if not api_key:
        raise ValueError("Marketaux API key is missing")

    params = {
        "api_token": api_key,
        "countries": countries,
        "language": language,
        "limit": limit,
        "filter_entities": "true"
    }

    response = requests.get(
        MARKETAUX_URL,
        params=params,
        timeout=30
    )

    if response.status_code != 200:
        raise ValueError(
            f"Marketaux API error: "
            f"{response.status_code} - {response.text}"
        )

    payload = response.json()

    articles = payload.get("data", [])

    if not articles:
        raise ValueError("No news data found")

    news_rows = []

    for article in articles:

        source = article.get("source", "")

        if isinstance(source, dict):
            source = source.get("name", "")

        news_rows.append({
            "title": article.get("title", ""),
            "description": article.get("description", ""),
            "source": source,
            "published_at": article.get("published_at", ""),
            "url": article.get("url", "")
        })

    df = pd.DataFrame(
        news_rows,
        columns=NEWS_COLUMNS
    )

    if df.empty:
        raise ValueError(
            "No valid news rows found"
        )

    return df


def save_news_csv(df: pd.DataFrame) -> None:
    """
    Save news data to CSV.
    """

    os.makedirs(
        "data/raw/news",
        exist_ok=True
    )

    filepath = (
        "data/raw/news/financial_news.csv"
    )

    df.to_csv(
        filepath,
        index=False
    )

    print(f"Saved -> {filepath}")


if __name__ == "__main__":

    BASE_DIR = Path(
        __file__
    ).resolve().parents[2]

    load_dotenv(
        BASE_DIR / ".env"
    )

    api_key = os.getenv(
        "MARKETAUX_API_KEY"
    )

    try:

        df = fetch_financial_news(
            api_key=api_key,
            countries="in",
            language="en",
            limit=50
        )

        print(
            f"News: {len(df)} rows fetched"
        )

        print("\nSample Headlines:\n")

        for title in df["title"].head(10):
            print(f"- {title}")

        save_news_csv(df)

    except Exception as e:

        print(f"News: {e}")