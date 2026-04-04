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
    momentum_above: float = 55.0,
) -> tuple[pd.Series, pd.Series]:
    """Enter when RSI crosses above threshold; exit when it crosses back below."""
    rsi = _rsi(df["Close"], period)
    above = rsi > momentum_above
    prev_above = above.shift(1).fillna(False)
    entry = (above & ~prev_above).fillna(False)
    exit_sig = (~above & prev_above).fillna(False)
    return entry.astype(bool), exit_sig.astype(bool)
