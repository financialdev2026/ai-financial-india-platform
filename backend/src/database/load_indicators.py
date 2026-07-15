import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine

engine = create_engine(
    "sqlite:///data/financial_market.db"
)


def load_indicators():

    indicator_folder = Path(
        "data/processed/indicators"
    )

    for file in indicator_folder.glob("*.csv"):

        ticker = file.stem.replace(
            "_indicators",
            ""
        )

        df = pd.read_csv(file)

        df = df.rename(columns={
            "Date": "date",
            "RSI": "rsi",

            "MACD": "macd",
            "MACD_signal": "macd_signal",
            "MACD_diff": "macd_histogram",

            "BB_high": "bb_upper",
            "BB_mid": "bb_middle",
            "BB_low": "bb_lower"
        })
        df["ticker"] = ticker

        df = df[
            [
                "ticker",
                "date",

                "rsi",

                "macd",
                "macd_signal",
                "macd_histogram",

                "bb_upper",
                "bb_middle",
                "bb_lower"
        ]
    ]

        df.to_sql(
            "technical_indicators",
            con=engine,
            if_exists="append",
            index=False
        )

        print(f"Loaded indicators for {ticker}")


if __name__ == "__main__":
    load_indicators()