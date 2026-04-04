import pandas as pd


def buy_hold(df: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    """Enter on the first bar's close (fill next open); hold until forced close at end."""
    ix = df.index
    entry = pd.Series(False, index=ix, dtype=bool)
    exit_sig = pd.Series(False, index=ix, dtype=bool)
    entry.iat[0] = True
    return entry, exit_sig
