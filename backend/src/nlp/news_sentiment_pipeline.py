import pandas as pd
from sqlalchemy import create_engine

from sentiment_model import analyze_sentiment_batch
from sector_mapping import SECTOR_KEYWORDS

engine = create_engine(
    "sqlite:///data/financial_market.db"
)


def detect_sector(text):

    text = str(text).upper()

    for sector, keywords in SECTOR_KEYWORDS.items():

        for keyword in keywords:

            if keyword in text:
                return sector

    return "UNKNOWN"


def process_news():

    news_df = pd.read_sql(
        "SELECT * FROM news",
        engine
    )

    print(
        f"Processing {len(news_df)} articles..."
    )

    texts = []
    meta = []
    for _, row in news_df.iterrows():
        title = str(row.get("title", ""))
        description = str(row.get("description", ""))
        text = title + " " + description
        texts.append(text[:512])
        meta.append({
            "title": title,
            "sector": detect_sector(text),
            "source": row.get("source", ""),
            "published_at": str(row.get("published_at", "")),
        })

    print(f"Calling Groq batch sentiment for {len(texts)} articles...")
    sentiments = analyze_sentiment_batch(texts)

    results = []
    for m, sent in zip(meta, sentiments):
        results.append({
            "title": m["title"],
            "sector": m["sector"],
            "sentiment": sent["label"],
            "confidence": sent["score"],
            "source": m["source"],
            "published_at": m["published_at"],
        })

    return pd.DataFrame(results)


from sqlalchemy import text

def save_results(df):

    with engine.begin() as conn:

        conn.execute(
            text(
                "DELETE FROM news_sentiment"
            )
        )

    df.to_sql(
        "news_sentiment",
        con=engine,
        if_exists="append",
        index=False
    )

    print(
        f"Saved {len(df)} sentiment records"
    )


if __name__ == "__main__":

    results = process_news()

    print("\nSample Results:\n")

    try:
        print(
            results.head()
        )
    except UnicodeEncodeError:
        print(
            results[["sector", "sentiment", "confidence"]].head()
        )

    save_results(results)