import os
import requests
import pandas as pd

NSE_HOME_URL = "https://www.nseindia.com"
NSE_FII_DII_URL = "https://www.nseindia.com/api/fiidiiTradeReact"

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": NSE_HOME_URL
}


def fetch_fii_dii_data() -> pd.DataFrame:
    """
    Fetch raw FII/DII flow data from NSE.
    """

    session = requests.Session()
    session.headers.update(HEADERS)

    session.get(NSE_HOME_URL, timeout=30)

    response = session.get(NSE_FII_DII_URL, timeout=30)

    if response.status_code != 200:
        raise ValueError(f"NSE API error: {response.status_code} - {response.text}")

    payload = response.json()

    if isinstance(payload, dict):
        records = payload.get("data", [])
    else:
        records = payload

    if not records:
        raise ValueError("No FII/DII data found")

    return pd.DataFrame(records)


def save_fii_dii_csv(df: pd.DataFrame) -> None:
    """
    Save raw FII/DII data to CSV.
    """

    if df.empty:
        raise ValueError("Cannot save empty FII/DII data")

    os.makedirs("data/raw/fii_dii", exist_ok=True)

    filepath = "data/raw/fii_dii/fii_dii_flows.csv"

    df.to_csv(filepath, index=False)

    print(f"Saved -> {filepath}")


if __name__ == "__main__":

    try:
        df = fetch_fii_dii_data()

        print(f"FII/DII: {len(df)} rows fetched")

        save_fii_dii_csv(df)

    except Exception as e:
        print(f"FII/DII: {e}")