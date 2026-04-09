from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf


def _normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.droplevel(1)
    df = df.dropna(how="all")
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


def validate_ohlcv(df: pd.DataFrame) -> None:
    """Validate OHLCV input data and raise clear errors if invalid."""
    required_cols = ["Open", "High", "Low", "Close", "Volume"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        raise ValueError(
            "Missing required OHLCV columns: "
            + ", ".join(missing_cols)
            + "."
        )

    missing_value_counts = df[required_cols].isna().sum()
    cols_with_missing = missing_value_counts[missing_value_counts > 0]
    if not cols_with_missing.empty:
        details = ", ".join(f"{col}={int(cnt)}" for col, cnt in cols_with_missing.items())
        raise ValueError(f"Found missing values in OHLCV columns: {details}.")

    if not df.index.is_monotonic_increasing:
        raise ValueError("Data index is not sorted in ascending timestamp order.")

    duplicate_mask = df.index.duplicated(keep=False)
    if duplicate_mask.any():
        dupes = pd.Index(df.index[duplicate_mask]).unique()
        sample = ", ".join(str(ts) for ts in dupes[:5])
        extra = "" if len(dupes) <= 5 else f" (+{len(dupes) - 5} more)"
        raise ValueError(f"Found duplicate timestamps in data index: {sample}{extra}.")


def fetch_tsla(
    start: str,
    end: str,
    *,
    interval: str = "1d",
    auto_adjust: bool = True,
    cache_path: str | Path | None = None,
) -> pd.DataFrame:
    """
    Load TSLA OHLCV. If `cache_path` points to an existing CSV, reads it
    (must have a date index and Close). Otherwise downloads from Yahoo Finance
    and, when `cache_path` is set, saves the result for offline reuse.

    Returns a DataFrame indexed by date with columns including Close.
    """
    cache = Path(cache_path) if cache_path else None
    if cache and cache.is_file():
        df = pd.read_csv(cache, index_col=0, parse_dates=True)
        df = _normalize_ohlcv(df)
        validate_ohlcv(df)
        return df

    df = yf.download(
        "TSLA",
        start=start,
        end=end,
        interval=interval,
        auto_adjust=auto_adjust,
        progress=False,
    )
    if df.empty:
        hint = ""
        if cache:
            hint = f" Or place a CSV at {cache} with columns Open,High,Low,Close,Volume."
        raise ValueError(
            f"No data returned for TSLA ({start=} {end=} {interval=}). "
            f"Yahoo may be rate-limiting; wait and retry.{hint}"
        )

    df = _normalize_ohlcv(df)
    validate_ohlcv(df)
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache)
    return df
