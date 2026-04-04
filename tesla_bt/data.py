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
    return df.sort_index()


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
        return _normalize_ohlcv(df)

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
    if cache:
        cache.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(cache)
    return df
