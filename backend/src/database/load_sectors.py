import pandas as pd
from pathlib import Path
from sqlalchemy import create_engine

engine = create_engine(
    "sqlite:///data/financial_market.db"
)


def load_sectors():

    sector_folder = Path("data/raw/sectors")

    for file in sector_folder.glob("*.csv"):

        sector = file.stem

        df = pd.read_csv(file)

        df = df.rename(columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })

        df["sector"] = sector

        df = df[
            [
                "sector",
                "date",
                "open",
                "high",
                "low",
                "close",
                "volume"
            ]
        ]

        df.to_sql(
            "sectors",
            con=engine,
            if_exists="append",
            index=False
        )

        print(f"Loaded {sector}")


if __name__ == "__main__":
    load_sectors()