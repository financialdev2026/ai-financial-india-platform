import os
import yfinance as yf
import pandas as pd

SECTORS = {
    "IT": "^CNXIT",
    "BANK": "^NSEBANK",
    "AUTO": "^CNXAUTO",
    "PHARMA": "^CNXPHARMA",
    "FMCG": "^CNXFMCG"
}


def fetch_sector_data(symbol: str, period: str = "1mo") -> pd.DataFrame:
    """
    Fetch sector index data from Yahoo Finance.
    """

    ticker = yf.Ticker(symbol)

    data = ticker.history(period=period)

    if data.empty:
        raise ValueError(f"No data found for {symbol}")

    return data


def save_sector_csv(df: pd.DataFrame, sector_name: str) -> None:
    """
    Save sector data to CSV.
    """

    os.makedirs("data/raw/sectors", exist_ok=True)

    filepath = f"data/raw/sectors/{sector_name}.csv"

    df.to_csv(filepath)

    print(f"Saved -> {filepath}")


if __name__ == "__main__":

    for sector_name, symbol in SECTORS.items():

        try:

            df = fetch_sector_data(symbol)

            print(f"{sector_name}: {len(df)} rows fetched")

            save_sector_csv(df, sector_name)

        except Exception as e:

            print(f"{sector_name}: {e}")