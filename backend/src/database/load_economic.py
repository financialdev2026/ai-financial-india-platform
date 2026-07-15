import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(
    "sqlite:///data/financial_market.db"
)


def load_economic():

    df = pd.read_csv(
        "data/raw/economic/economic_indicators.csv"
    )

    df = df[
        [
            "date",
            "indicator",
            "value",
            "source"
        ]
    ]

    df.to_sql(
        "economic_data",
        con=engine,
        if_exists="append",
        index=False
    )

    print(
        f"Loaded {len(df)} economic records"
    )


if __name__ == "__main__":
    load_economic()