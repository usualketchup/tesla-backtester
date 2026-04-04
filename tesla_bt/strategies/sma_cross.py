import pandas as pd


def sma_crossover(df: pd.DataFrame, fast: int = 20, slow: int = 50) -> tuple[pd.Series, pd.Series]:
    """Enter on bullish SMA cross; exit on bearish cross."""
    close = df["Close"]
    fast_ma = close.rolling(fast, min_periods=fast).mean()
    slow_ma = close.rolling(slow, min_periods=slow).mean()
    long = fast_ma >= slow_ma
    prev_long = long.shift(1).fillna(False)
    entry = (long & ~prev_long).fillna(False)
    exit_sig = (~long & prev_long).fillna(False)
    return entry.astype(bool), exit_sig.astype(bool)
