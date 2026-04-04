from __future__ import annotations

import pandas as pd

from tesla_bt.engine import run_backtest
from tesla_bt.indicators import add_vwap
from tesla_bt.metrics import summarize_backtest
from tesla_bt.strategies.protocols import Strategy


def compare_strategies(
    df: pd.DataFrame,
    strategies: dict[str, Strategy],
    *,
    initial_capital: float = 100_000.0,
    commission_rate: float = 0.0,
) -> pd.DataFrame:
    """
    Run each strategy on the same OHLCV DataFrame and return a metrics table
    sorted by total return (descending).

    Each strategy returns ``entry_signal`` and ``exit_signal`` as boolean
    ``pd.Series`` aligned with ``df.index``.

    A ``vwap`` column is added (see :func:`tesla_bt.indicators.add_vwap`) so
    strategies can use ``df["vwap"]`` without mutating the caller's frame.
    """
    df = add_vwap(df)
    open_ = df["Open"]
    close = df["Close"]
    rows: list[dict[str, float | str]] = []
    for name, fn in strategies.items():
        entry_signal, exit_signal = fn(df)
        result = run_backtest(
            open_,
            close,
            entry_signal,
            exit_signal,
            commission_rate=commission_rate,
        )
        m = summarize_backtest(
            result["trades"],
            result["equity_curve"],
            initial_capital=initial_capital,
        )
        m["strategy"] = name
        rows.append(m)

    out = pd.DataFrame(rows).set_index("strategy")
    out = out.sort_values("total_return", ascending=False)
    return out
