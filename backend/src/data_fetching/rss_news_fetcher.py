import os
import feedparser
import pandas as pd

RSS_FEEDS = {

    "Moneycontrol":
    "https://www.moneycontrol.com/rss/business.xml",

    "Business Standard":
    "https://www.business-standard.com/rss/markets-106.rss",

    "Livemint":
    "https://www.livemint.com/rss/markets",

    "Economic Times":
    "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms"
}


def fetch_rss_news():

    all_news = []

    for source_name, feed_url in RSS_FEEDS.items():

        try:

            feed = feedparser.parse(feed_url)

            for entry in feed.entries:

                all_news.append({

                    "title":
                    getattr(entry, "title", ""),

                    "description":
                    getattr(entry, "summary", ""),

                    "source":
                    source_name,

                    "published_at":
                    getattr(entry, "published", ""),

                    "url":
                    getattr(entry, "link", "")
                })

            print(
                f"{source_name}: "
                f"{len(feed.entries)} articles"
            )

        except Exception as e:

            print(
                f"{source_name}: {e}"
            )

    return pd.DataFrame(all_news)


def save_rss_news(df):

    os.makedirs(
        "data/raw/news",
        exist_ok=True
    )

    filepath = (
        "data/raw/news/rss_news.csv"
    )

    df.to_csv(
        filepath,
        index=False
    )

    print(
        f"Saved -> {filepath}"
    )


if __name__ == "__main__":

    df = fetch_rss_news()

    print(
        f"\nRSS News: {len(df)} rows"
    )

    save_rss_news(df)