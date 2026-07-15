import os
import re
import pandas as pd


INPUT_FILES = [
    "data/raw/news/financial_news.csv",
    "data/raw/news/rss_news.csv"
]

OUTPUT_FILE = "data/raw/news/final_news.csv"


def normalize_title(title):

    if pd.isna(title):
        return ""

    title = str(title).lower()

    title = re.sub(
        r"[^\w\s]",
        "",
        title
    )

    title = " ".join(
        title.split()
    )

    return title


def load_news_files():

    dfs = []

    for file in INPUT_FILES:

        if os.path.exists(file):

            df = pd.read_csv(file)

            print(
                f"Loaded {file} "
                f"({len(df)} rows)"
            )

            dfs.append(df)

        else:

            print(
                f"Skipped missing file: {file}"
            )

    if not dfs:

        raise ValueError(
            "No news files found."
        )

    return dfs


def merge_and_deduplicate():

    dfs = load_news_files()

    merged = pd.concat(
        dfs,
        ignore_index=True
    )

    original_count = len(merged)

    print(
        f"\nOriginal Count: "
        f"{original_count}"
    )

    # URL deduplication
    if "url" in merged.columns:

        merged.drop_duplicates(
            subset=["url"],
            inplace=True
        )

    after_url_count = len(merged)

    print(
        f"After URL Dedup: "
        f"{after_url_count}"
    )

    # Title normalization
    merged["normalized_title"] = (
        merged["title"]
        .astype(str)
        .apply(normalize_title)
    )

    merged.drop_duplicates(
        subset=["normalized_title"],
        inplace=True
    )

    after_title_count = len(merged)

    print(
        f"After Title Dedup: "
        f"{after_title_count}"
    )

    merged.drop(
        columns=["normalized_title"],
        inplace=True
    )

    # Sort by publication date if available
    if "published_at" in merged.columns:

        try:

            merged["published_at"] = pd.to_datetime(
                merged["published_at"],
                errors="coerce"
            )

            merged = merged.sort_values(
                by="published_at",
                ascending=False
            )

        except Exception:
            pass

    merged.reset_index(
        drop=True,
        inplace=True
    )

    duplicates_removed = (
        original_count -
        len(merged)
    )

    print(
        f"Duplicates Removed: "
        f"{duplicates_removed}"
    )

    print(
        f"Final News Count: "
        f"{len(merged)}"
    )

    return merged


def save_final_news(df):

    os.makedirs(
        "data/raw/news",
        exist_ok=True
    )

    df.to_csv(
        OUTPUT_FILE,
        index=False
    )

    print(
        f"\nSaved -> "
        f"{OUTPUT_FILE}"
    )


if __name__ == "__main__":

    final_news = merge_and_deduplicate()

    save_final_news(final_news)