import math
from typing import Iterable, Optional

import pandas as pd


def parse_datetime(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce", utc=True).dt.tz_convert(None)


def parse_date_column(df: pd.DataFrame, column: str = "date") -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return df.copy()

    output = df.copy()
    output["_parsed_date"] = parse_datetime(output[column])
    return output


def latest_rows(df: pd.DataFrame, date_column: str = "date") -> pd.DataFrame:
    output = parse_date_column(df, date_column)
    if output.empty or "_parsed_date" not in output.columns:
        return output

    latest_date = output["_parsed_date"].max()
    return output[output["_parsed_date"] == latest_date].copy()


def latest_per_group(
    df: pd.DataFrame,
    group_column: str,
    date_column: str = "date",
    required_columns: Optional[Iterable[str]] = None,
) -> pd.DataFrame:
    output = parse_date_column(df, date_column)
    if output.empty:
        return output

    if required_columns:
        for column in required_columns:
            if column in output.columns:
                output = output[output[column].notna()]

    if output.empty:
        return output

    output = output.sort_values([group_column, "_parsed_date"])
    return output.groupby(group_column, as_index=False).tail(1).copy()


def bounded_mean(series: pd.Series, default: float = 0.0) -> float:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return default
    return float(clean.mean())


def recency_weight(age_days: float, half_life_days: float = 3.0) -> float:
    if pd.isna(age_days) or age_days < 0:
        return 1.0
    if half_life_days <= 0:
        return 1.0
    return math.pow(0.5, age_days / half_life_days)


def weighted_average(values: pd.Series, weights: pd.Series, default: float = 0.0) -> float:
    values = pd.to_numeric(values, errors="coerce")
    weights = pd.to_numeric(weights, errors="coerce")
    mask = values.notna() & weights.notna() & (weights > 0)
    if not mask.any():
        return default
    return float((values[mask] * weights[mask]).sum() / weights[mask].sum())


def iso_date(value) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return ""
    return parsed.strftime("%Y-%m-%d")
