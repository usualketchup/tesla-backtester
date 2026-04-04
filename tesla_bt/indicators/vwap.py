from __future__ import annotations

import numpy as np
import pandas as pd


def add_vwap(
    df: pd.DataFrame,
    *,
    inplace: bool = False,
    high: str = "High",
    low: str = "Low",
    close: str = "Close",
    volume: str = "Volume",
) -> pd.DataFrame:
    """
    Append a ``VWAP`` column using typical price and volume.

    ``typical_price = (High + Low + Close) / 3``  
    ``VWAP = cumulative(typical_price * volume) / cumulative(volume)``

    When the index is a ``DatetimeIndex``, cumulatives reset at each calendar
    day (ready for intraday bars). Otherwise all rows share one cumulative
    session (no daily boundary).

    Zero-volume cumulatives yield NaN for that segment until volume accrues.

    Parameters
    ----------
    df
        Must contain the OHLCV columns (names configurable).
    inplace
        If True, mutate ``df`` and return it; if False, return a copy.
    """
    target = df if inplace else df.copy()

    tp = (target[high].astype(float) + target[low].astype(float) + target[close].astype(float)) / 3.0
    pv = tp * target[volume].astype(float)

    if isinstance(target.index, pd.DatetimeIndex):
        day_key = target.index.normalize()
    else:
        day_key = pd.Series(0, index=target.index, dtype=np.int64)

    aux = pd.DataFrame({"_pv": pv, "_v": target[volume].astype(float), "_day": day_key}, index=target.index)
    cum_pv = aux.groupby("_day", sort=False)["_pv"].cumsum()
    cum_v = aux.groupby("_day", sort=False)["_v"].cumsum()

    target["vwap"] = cum_pv / cum_v.replace(0.0, np.nan)
    return target
