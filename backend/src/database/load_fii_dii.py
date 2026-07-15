import pandas as pd
from sqlalchemy import create_engine

engine = create_engine(
    "sqlite:///data/financial_market.db"
)


def load_fii_dii():

    df = pd.read_csv(
        "data/raw/fii_dii/fii_dii_flows.csv"
    )

    df = df.rename(columns={
        "category": "client_type",
        "buyValue": "buy_value",
        "sellValue": "sell_value",
        "netValue": "net_value"
    })

    df = df[
        [
            "date",
            "client_type",
            "buy_value",
            "sell_value",
            "net_value"
        ]
    ]

    df.to_sql(
        "fii_dii",
        con=engine,
        if_exists="append",
        index=False
    )

    print(f"Loaded {len(df)} FII/DII records")


if __name__ == "__main__":
    load_fii_dii()