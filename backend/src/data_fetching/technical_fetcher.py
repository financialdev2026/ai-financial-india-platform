import os
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import BollingerBands

RAW_STOCKS_DIR = "data/raw/stocks"
PROCESSED_INDICATORS_DIR = "data/processed/indicators"


def load_stock_csv(filepath: str) -> pd.DataFrame:
    """
    Load raw stock data from CSV.
    """

    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Stock file not found: {filepath}")

    data = pd.read_csv(filepath)

    if data.empty:
        raise ValueError(f"Stock file is empty: {filepath}")

    if "Close" not in data.columns:
        raise ValueError(f"Missing Close column in: {filepath}")

    return data


def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add RSI, MACD, and Bollinger Bands to stock data.
    """

    data = df.copy()

    close = data["Close"]

    rsi = RSIIndicator(close=close, window=14)
    data["RSI"] = rsi.rsi()

    macd = MACD(close=close)
    data["MACD"] = macd.macd()
    data["MACD_signal"] = macd.macd_signal()
    data["MACD_diff"] = macd.macd_diff()

    bollinger = BollingerBands(close=close, window=20, window_dev=2)
    data["BB_high"] = bollinger.bollinger_hband()
    data["BB_mid"] = bollinger.bollinger_mavg()
    data["BB_low"] = bollinger.bollinger_lband()

    return data


def save_indicators_csv(df: pd.DataFrame, filename: str) -> None:
    """
    Save stock data with technical indicators to CSV.
    """

    os.makedirs(PROCESSED_INDICATORS_DIR, exist_ok=True)

    filepath = os.path.join(PROCESSED_INDICATORS_DIR, filename)

    df.to_csv(filepath, index=False)

    print(f"Saved -> {filepath}")


def process_stock_file(filepath: str) -> None:
    """
    Process one raw stock CSV file.
    """

    filename = os.path.basename(filepath)

    df = load_stock_csv(filepath)

    indicator_df = add_technical_indicators(df)

    save_indicators_csv(indicator_df, filename)


if __name__ == "__main__":

    try:
        if not os.path.exists(RAW_STOCKS_DIR):
            raise FileNotFoundError(f"Raw stocks folder not found: {RAW_STOCKS_DIR}")

        stock_files = [
            os.path.join(RAW_STOCKS_DIR, filename)
            for filename in os.listdir(RAW_STOCKS_DIR)
            if filename.endswith(".csv")
        ]

        if not stock_files:
            raise ValueError("No stock CSV files found")

        for filepath in stock_files:

            try:
                process_stock_file(filepath)

            except Exception as e:
                print(f"{filepath}: {e}")

    except Exception as e:
        print(f"Technical indicators: {e}")