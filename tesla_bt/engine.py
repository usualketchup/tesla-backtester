from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

r"""
Trade-based long-only backtest.

Execution: signals observed at bar close; orders fill at the *next* bar's open.
Equity is marked to market at each bar's close (cash + shares * close).

Commission applies to each fill as a fraction of fill notional (buy and sell).
"""


def _align_bool(s: pd.Series, index: pd.Index) -> pd.Series:
    out = s.reindex(index)
    return out.fillna(False).astype(bool)


def _open_notional_to_shares(cash: float, open_px: float, commission_rate: float) -> tuple[float, float]:
    """Spend all cash on shares at open; return (shares, remaining_cash)."""
    notional = cash * (1.0 - commission_rate)
    if open_px <= 0 or notional <= 0:
        return 0.0, cash
    shares = notional / open_px
    return shares, 0.0


def _liquidate_at_open(
    shares: float, open_px: float, commission_rate: float
) -> float:
    """Sell all shares at open; return cash proceeds."""
    if shares <= 0 or open_px <= 0:
        return 0.0
    return float(shares * open_px * (1.0 - commission_rate))


@dataclass
class _ActiveTrade:
    entry_time: pd.Timestamp
    entry_price: float
    entry_equity: float


@dataclass
class _Portfolio:
    cash: float
    shares: float
    in_position: bool = False
    active: _ActiveTrade | None = None
    pending_enter: bool = False
    pending_exit: bool = False


def _equity_at_close(portfolio: _Portfolio, close_px: float) -> float:
    return float(portfolio.cash + portfolio.shares * close_px)


def _execute_exit_at_open(
    portfolio: _Portfolio,
    open_px: float,
    commission_rate: float,
    exit_time: pd.Timestamp,
    trades_out: list[dict[str, Any]],
) -> None:
    proceeds = _liquidate_at_open(portfolio.shares, open_px, commission_rate)
    assert portfolio.active is not None
    ret_pct = float(proceeds / portfolio.active.entry_equity - 1.0) if portfolio.active.entry_equity else 0.0
    trades_out.append(
        {
            "entry_time": portfolio.active.entry_time,
            "entry_price": portfolio.active.entry_price,
            "exit_time": exit_time,
            "exit_price": float(open_px),
            "return_pct": ret_pct,
        }
    )
    portfolio.cash = proceeds
    portfolio.shares = 0.0
    portfolio.in_position = False
    portfolio.active = None


def _execute_entry_at_open(
    portfolio: _Portfolio,
    open_px: float,
    commission_rate: float,
    entry_time: pd.Timestamp,
) -> None:
    entry_equity = portfolio.cash
    shares, cash_rem = _open_notional_to_shares(portfolio.cash, open_px, commission_rate)
    portfolio.shares = shares
    portfolio.cash = cash_rem
    portfolio.in_position = True
    portfolio.active = _ActiveTrade(
        entry_time=entry_time,
        entry_price=float(open_px),
        entry_equity=float(entry_equity),
    )


def run_backtest(
    open_: pd.Series,
    close: pd.Series,
    entry_signal: pd.Series,
    exit_signal: pd.Series,
    *,
    commission_rate: float = 0.0,
    force_close_last: bool = True,
) -> dict[str, pd.DataFrame | pd.Series]:
    """
    Run a long-only trade simulation.

    Parameters
    ----------
    open_, close
        Bar open and close, aligned on the same DatetimeIndex (or any shared index).
    entry_signal, exit_signal
        Boolean-like Series aligned to that index. True means "request action"
        evaluated at that bar's close; the fill occurs at the *next* bar's open.
        If both apply while flat, only entry is scheduled. While in a position,
        exit takes precedence over entry.

    commission_rate
        Fraction charged on each fill's notional (entry and exit).

    force_close_last
        If True, any open position is closed at the last bar's *close* so the
        equity curve and trade log are flat at the end. An ``entry_signal`` on
        the final bar cannot fill (no following open); use a longer history or
        accept that the last entry is ignored.

    Returns
    -------
    dict with:
        ``trades`` : DataFrame (entry_time, entry_price, exit_time, exit_price, return_pct)
        ``equity_curve`` : Series (starts at 1.0, indexed like input)
        ``returns`` : Series of per-bar simple returns on equity (first bar NaN)
    """
    index = open_.index
    open_ = open_.astype(float).reindex(index)
    close = close.astype(float).reindex(index)
    entry_signal = _align_bool(entry_signal, index)
    exit_signal = _align_bool(exit_signal, index)

    n = len(index)
    if n == 0:
        empty_trades = pd.DataFrame(
            columns=["entry_time", "entry_price", "exit_time", "exit_price", "return_pct"]
        )
        return {
            "trades": empty_trades,
            "equity_curve": pd.Series(dtype=float),
            "returns": pd.Series(dtype=float),
        }

    portfolio = _Portfolio(cash=1.0, shares=0.0)
    trades_out: list[dict[str, Any]] = []
    equity_vals: list[float] = []

    for t in range(n):
        o = float(open_.iloc[t])
        c = float(close.iloc[t])
        ts = index[t]

        if t > 0:
            if portfolio.pending_exit and portfolio.in_position:
                _execute_exit_at_open(portfolio, o, commission_rate, ts, trades_out)
                portfolio.pending_exit = False
            if portfolio.pending_enter and not portfolio.in_position:
                _execute_entry_at_open(portfolio, o, commission_rate, ts)
                portfolio.pending_enter = False

        eq = _equity_at_close(portfolio, c)
        equity_vals.append(eq)

        if portfolio.in_position:
            portfolio.pending_exit = bool(exit_signal.iloc[t])
            portfolio.pending_enter = False
        else:
            portfolio.pending_enter = bool(entry_signal.iloc[t])
            portfolio.pending_exit = False

    equity_curve = pd.Series(equity_vals, index=index, dtype=float, name="equity")

    if force_close_last and portfolio.in_position and portfolio.active is not None:
        last_c = float(close.iloc[-1])
        last_ts = index[-1]
        proceeds = _liquidate_at_open(portfolio.shares, last_c, commission_rate)
        ret_pct = (
            float(proceeds / portfolio.active.entry_equity - 1.0)
            if portfolio.active.entry_equity
            else 0.0
        )
        trades_out.append(
            {
                "entry_time": portfolio.active.entry_time,
                "entry_price": portfolio.active.entry_price,
                "exit_time": last_ts,
                "exit_price": last_c,
                "return_pct": ret_pct,
            }
        )
        portfolio.cash = proceeds
        portfolio.shares = 0.0
        portfolio.in_position = False
        portfolio.active = None
        equity_curve.iloc[-1] = portfolio.cash

    returns = equity_curve.pct_change()

    trades_df = pd.DataFrame(trades_out)
    if not trades_df.empty:
        for col in ("entry_time", "exit_time"):
            trades_df[col] = pd.to_datetime(trades_df[col])

    return {
        "trades": trades_df,
        "equity_curve": equity_curve,
        "returns": returns,
    }
