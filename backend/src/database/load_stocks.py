import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine

engine = create_engine(
    "sqlite:///data/financial_market.db"
)

def load_stocks():

    stock_folder = Path("data/raw/stocks")

    for file in stock_folder.glob("*.csv"):

        ticker = file.stem

        df = pd.read_csv(file)

        df = df.rename(columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })

        df["ticker"] = ticker

        df = df[
            [
                "ticker",
                "date",
                "open",
                "high",
                "low",
                "close",
                "volume"
            ]
        ]

        df.to_sql(
            "stocks",
            con=engine,
            if_exists="append",
            index=False
        )

        print(f"Loaded {ticker}")

if __name__ == "__main__":
    load_stocks()