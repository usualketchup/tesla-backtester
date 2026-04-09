import pandas as pd


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    return 100 - (100 / (1 + rs))


def rsi_threshold(
    df: pd.DataFrame,
    period: int = 14,
    entry_level: float = 55.0,
    exit_level: float = 50.0,
) -> tuple[pd.Series, pd.Series]:
    """
    Entry when RSI crosses above ``entry_level`` (default 55).
    Exit when RSI crosses below ``exit_level`` (default 50).
    """
    rsi = _rsi(df["Close"], period)
    prev = rsi.shift(1)

    entry_signal = ((rsi > entry_level) & (prev <= entry_level)).fillna(False).astype(bool)
    exit_signal = ((rsi < exit_level) & (prev >= exit_level)).fillna(False).astype(bool)

    # Shift signals by one bar so decisions use only prior-bar information (prevents lookahead bias).
    entry_signal = entry_signal.shift(1).fillna(False).astype(bool)
    exit_signal = exit_signal.shift(1).fillna(False).astype(bool)

    return entry_signal, exit_signal
