import pandas as pd


def sma_crossover(df: pd.DataFrame, fast: int = 20, slow: int = 50) -> tuple[pd.Series, pd.Series]:
    """
    Entry when fast SMA crosses strictly above slow SMA.
    Exit when fast SMA crosses strictly below slow SMA.
    """
    close = df["Close"]
    fast_ma = close.rolling(fast, min_periods=fast).mean()
    slow_ma = close.rolling(slow, min_periods=slow).mean()
    prev_fast = fast_ma.shift(1)
    prev_slow = slow_ma.shift(1)

    entry_signal = (
        (fast_ma > slow_ma) & (prev_fast <= prev_slow)
    ).fillna(False).astype(bool)

    exit_signal = (
        (fast_ma < slow_ma) & (prev_fast >= prev_slow)
    ).fillna(False).astype(bool)

    # Shift signals by one bar so decisions use only prior-bar information (prevents lookahead bias).
    entry_signal = entry_signal.shift(1).fillna(False).astype(bool)
    exit_signal = exit_signal.shift(1).fillna(False).astype(bool)

    return entry_signal, exit_signal
