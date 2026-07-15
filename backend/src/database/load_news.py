import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(
    "sqlite:///data/financial_market.db"
)

df = pd.read_csv(
    "data/raw/news/final_news.csv"
)

print(f"Loaded {len(df)} news records")

df.to_sql(
    "news",
    con=engine,
    if_exists="append",
    index=False
)

print("News data inserted successfully")