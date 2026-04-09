import pandas as pd


def buy_hold(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """
    ``entry_signal``: True only on the first row (fill on next bar open).
    ``exit_signal``: False for all rows (position closed only by engine ``force_close_last``).
    """
    ix = df.index
    entry_signal = pd.Series(False, index=ix, dtype=bool)
    exit_signal = pd.Series(False, index=ix, dtype=bool)
    if len(ix) > 0:
        entry_signal.iat[0] = True
    # Shift signals by one bar so decisions use only prior-bar information (prevents lookahead bias).
    entry_signal = entry_signal.shift(1).fillna(False).astype(bool)
    exit_signal = exit_signal.shift(1).fillna(False).astype(bool)
    return entry_signal, exit_signal
