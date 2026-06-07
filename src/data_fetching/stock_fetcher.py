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


def fetch_stock_data(symbol: str, period: str = "1mo") -> pd.DataFrame:
    """
    Fetch stock data from Yahoo Finance.
    """

    ticker = yf.Ticker(symbol)
    data = ticker.history(period=period)

    if data.empty:
        raise ValueError(f"No data found for {symbol}")

    return data


def save_to_csv(df: pd.DataFrame, symbol: str) -> None:
    """
    Save stock data to CSV.
    """

    os.makedirs("data/raw", exist_ok=True)

    filename = symbol.replace(".NS", "")
    filepath = f"data/raw/{filename}.csv"

    df.to_csv(filepath)

    print(f"Saved -> {filepath}")


if __name__ == "__main__":

    for stock in TOP_STOCKS:

        try:
            df = fetch_stock_data(stock)

            print(f"{stock}: {len(df)} rows fetched")

            save_to_csv(df, stock)

        except Exception as e:
            print(f"{stock}: {e}")