from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

r"""
Trade-based long-only backtest.

Execution: signals observed at bar close; orders fill at the *next* bar's open.
Equity is marked to market at each bar's close (cash + shares * close).

Optional stop-loss / take-profit use the bar's High/Low (intrabar). If both
levels trade in the same candle, stop loss is assumed first (conservative).

Slippage worsens fills: long entry pays ``price * (1 + slippage_pct)``, exits
receive ``price * (1 - slippage_pct)`` on the model fill price.

Commission applies to each fill as a fraction of fill notional (buy and sell).
"""


def _slipped_entry_price(raw: float, slippage_pct: float) -> float:
    return float(raw * (1.0 + slippage_pct))


def _slipped_exit_price(raw: float, slippage_pct: float) -> float:
    return float(raw * (1.0 - slippage_pct))


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


def _proceeds_from_sell(shares: float, fill_px: float, commission_rate: float) -> float:
    if shares <= 0 or fill_px <= 0:
        return 0.0
    return float(shares * fill_px * (1.0 - commission_rate))


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


def _finalize_exit(
    portfolio: _Portfolio,
    raw_exit_px: float,
    commission_rate: float,
    slippage_pct: float,
    exit_time: pd.Timestamp,
    trades_out: list[dict[str, Any]],
    exit_reason: str,
) -> None:
    fill_px = _slipped_exit_price(raw_exit_px, slippage_pct)
    proceeds = _proceeds_from_sell(portfolio.shares, fill_px, commission_rate)
    assert portfolio.active is not None
    ret_pct = (
        float(proceeds / portfolio.active.entry_equity - 1.0) if portfolio.active.entry_equity else 0.0
    )
    trades_out.append(
        {
            "entry_time": portfolio.active.entry_time,
            "entry_price": portfolio.active.entry_price,
            "exit_time": exit_time,
            "exit_price": float(fill_px),
            "return_pct": ret_pct,
            "exit_reason": exit_reason,
        }
    )
    portfolio.cash = proceeds
    portfolio.shares = 0.0
    portfolio.in_position = False
    portfolio.active = None


def _intrabar_stop_tp_long(
    entry_price: float,
    open_px: float,
    high: float,
    low: float,
    stop_loss_pct: float | None,
    take_profit_pct: float | None,
) -> tuple[float | None, str | None]:
    """
    If stop or take-profit is touched this bar, return (fill_price, reason).
    If both touch, stop loss wins; long stop fill uses min(open, stop_level),
    long TP fill uses max(open, tp_level) (gaps through the level).
    """
    stop_level: float | None = None
    tp_level: float | None = None
    if stop_loss_pct is not None and stop_loss_pct > 0:
        stop_level = entry_price * (1.0 - stop_loss_pct)
    if take_profit_pct is not None and take_profit_pct > 0:
        tp_level = entry_price * (1.0 + take_profit_pct)

    stop_hit = stop_level is not None and low <= stop_level
    tp_hit = tp_level is not None and high >= tp_level

    if stop_hit and tp_hit:
        return min(open_px, stop_level), "stop_loss"
    if stop_hit:
        assert stop_level is not None
        return min(open_px, stop_level), "stop_loss"
    if tp_hit:
        assert tp_level is not None
        return max(open_px, tp_level), "take_profit"
    return None, None


def _execute_entry_at_open(
    portfolio: _Portfolio,
    open_px: float,
    commission_rate: float,
    slippage_pct: float,
    entry_time: pd.Timestamp,
) -> None:
    entry_equity = portfolio.cash
    fill_px = _slipped_entry_price(open_px, slippage_pct)
    shares, cash_rem = _open_notional_to_shares(portfolio.cash, fill_px, commission_rate)
    portfolio.shares = shares
    portfolio.cash = cash_rem
    portfolio.in_position = True
    portfolio.active = _ActiveTrade(
        entry_time=entry_time,
        entry_price=float(fill_px),
        entry_equity=float(entry_equity),
    )


def run_backtest(
    open_: pd.Series,
    close: pd.Series,
    entry_signal: pd.Series,
    exit_signal: pd.Series,
    *,
    high: pd.Series | None = None,
    low: pd.Series | None = None,
    stop_loss_pct: float | None = None,
    take_profit_pct: float | None = None,
    commission_rate: float = 0.0,
    slippage_pct: float = 0.001,
    force_close_last: bool = True,
) -> dict[str, pd.DataFrame | pd.Series]:
    """
    Run a long-only trade simulation.

    Parameters
    ----------
    open_, close
        Bar open and close, aligned on the same index.
    high, low
        Bar high and low for intrabar stop / take-profit. Required when
        ``stop_loss_pct`` or ``take_profit_pct`` is set (positive); otherwise
        may be omitted (defaults to ``close``).
    entry_signal, exit_signal
        Boolean-like Series aligned to that index. True means "request action"
        evaluated at that bar's close; the fill occurs at the *next* bar's open.
        If both apply while flat, only entry is scheduled. While in a position,
        exit takes precedence over entry.

    stop_loss_pct, take_profit_pct
        If set and positive, exit long immediately when the bar's range shows
        the level was touched: stop if ``Low <= entry * (1 - stop_loss_pct)``,
        take profit if ``High >= entry * (1 + take_profit_pct)``. If both
        occur in one bar, stop is processed first.

    commission_rate
        Fraction charged on each fill's notional (entry and exit).

    slippage_pct
        Adverse fill adjustment: buys at ``raw * (1 + slippage_pct)``, sells at
        ``raw * (1 - slippage_pct)`` for signal, stop-loss, take-profit, and
        end-of-data exits.

    force_close_last
        If True, any open position is closed at the last bar's *close* so the
        equity curve and trade log are flat at the end. An ``entry_signal`` on
        the final bar cannot fill (no following open); use a longer history or
        accept that the last entry is ignored.

    Returns
    -------
    dict with:
        ``trades`` : DataFrame (entry_time, entry_price, exit_time, exit_price,
            return_pct, exit_reason)
        ``equity_curve`` : Series (starts at 1.0, indexed like input)
        ``returns`` : Series of per-bar simple returns on equity (first bar NaN)
    """
    index = open_.index
    open_ = open_.astype(float).reindex(index)
    close = close.astype(float).reindex(index)

    sl_on = stop_loss_pct is not None and stop_loss_pct > 0
    tp_on = take_profit_pct is not None and take_profit_pct > 0
    if sl_on or tp_on:
        if high is None or low is None:
            raise ValueError("high and low are required when stop_loss_pct or take_profit_pct is set.")
        high_s = high.astype(float).reindex(index)
        low_s = low.astype(float).reindex(index)
    else:
        high_s = close
        low_s = close

    entry_signal = _align_bool(entry_signal, index)
    exit_signal = _align_bool(exit_signal, index)

    n = len(index)
    if n == 0:
        empty_trades = pd.DataFrame(
            columns=[
                "entry_time",
                "entry_price",
                "exit_time",
                "exit_price",
                "return_pct",
                "exit_reason",
            ]
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
        hi = float(high_s.iloc[t])
        lo = float(low_s.iloc[t])
        ts = index[t]

        if t > 0:
            if portfolio.pending_exit and portfolio.in_position:
                _finalize_exit(portfolio, o, commission_rate, slippage_pct, ts, trades_out, "signal")
                portfolio.pending_exit = False
            if portfolio.pending_enter and not portfolio.in_position:
                _execute_entry_at_open(portfolio, o, commission_rate, slippage_pct, ts)
                portfolio.pending_enter = False

        if portfolio.in_position and portfolio.active is not None:
            fill, reason = _intrabar_stop_tp_long(
                portfolio.active.entry_price,
                o,
                hi,
                lo,
                stop_loss_pct if sl_on else None,
                take_profit_pct if tp_on else None,
            )
            if fill is not None and reason is not None:
                portfolio.pending_exit = False
                _finalize_exit(portfolio, fill, commission_rate, slippage_pct, ts, trades_out, reason)

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
        _finalize_exit(portfolio, last_c, commission_rate, slippage_pct, last_ts, trades_out, "signal")
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
