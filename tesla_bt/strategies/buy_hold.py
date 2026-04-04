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
    return entry_signal, exit_signal
