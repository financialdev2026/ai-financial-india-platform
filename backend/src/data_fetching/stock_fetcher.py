import os
import yfinance as yf
import pandas as pd

TOP_STOCKS = [
    "RELIANCE.NS",
    "TCS.NS",
    "INFY.NS",
    "HDFCBANK.NS",
    "ICICIBANK.NS",
    "SBIN.NS",
    "ITC.NS",
    "LT.NS",
    "BHARTIARTL.NS",
    "HINDUNILVR.NS"
]


def fetch_stock_data(symbol: str, period: str = "2y") -> pd.DataFrame:
    """
    Fetch one year of daily stock data from Yahoo Finance.
    """

    ticker = yf.Ticker(symbol)

    data = ticker.history(
        period=period,
        interval="1d",
        auto_adjust=False
    )

    if data.empty:
        raise ValueError(f"No data found for {symbol}")

    data.reset_index(inplace=True)

    data["Date"] = pd.to_datetime(data["Date"]).dt.tz_localize(None)

    return data


def save_to_csv(df: pd.DataFrame, symbol: str) -> None:
    """
    Save stock data to CSV.
    """

    os.makedirs("data/raw/stocks", exist_ok=True)

    filename = symbol.replace(".NS", "")

    filepath = f"data/raw/stocks/{filename}.csv"

    df.to_csv(
        filepath,
        index=False
    )

    print(f"Saved -> {filepath}")


if __name__ == "__main__":

    print("\nFetching Stock Data...\n")

    for stock in TOP_STOCKS:

        try:

            df = fetch_stock_data(stock)

            print(f"{stock}: {len(df)} trading days fetched")

            save_to_csv(df, stock)

        except Exception as e:

            print(f"{stock}: {e}")

    print("\nStock data fetching completed.")