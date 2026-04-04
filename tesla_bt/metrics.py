from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    peak = equity.cummax()
    dd = (equity / peak) - 1.0
    return float(dd.min())


def summarize_backtest(
    trades_df: pd.DataFrame,
    equity_curve: pd.Series,
    *,
    initial_capital: float = 100_000.0,
) -> dict[str, float]:
    """
    Summarize a trade-based backtest from closed trades and the equity curve.

    Trade metrics use ``return_pct`` per row. ``average_loss`` is the mean
    **magnitude** of losing trades (positive number). Expectancy follows
    ``(win_rate * average_win) - ((1 - win_rate) * average_loss)``.

    ``final_equity`` scales the ending equity to ``initial_capital`` when the
    curve starts at 1.0.
    """
    equity = equity_curve.dropna()
    returns = equity_curve.pct_change().dropna()

    base = float(equity.iloc[0]) if len(equity) else 1.0
    scale = initial_capital / base if base else initial_capital

    if equity.empty:
        return _empty_summary(scale, base)

    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    n_bars = len(returns)
    years = n_bars / TRADING_DAYS
    cagr = (
        float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1.0) if years > 0 else 0.0
    )
    max_dd = _max_drawdown(equity)

    if len(returns) < 2:
        sharpe = 0.0
    else:
        daily_vol = float(returns.std(ddof=1))
        mean_daily = float(returns.mean())
        sharpe = float(
            (mean_daily / daily_vol) * np.sqrt(TRADING_DAYS) if daily_vol > 0 else 0.0
        )

    trade_metrics = _trade_metrics(trades_df)

    out: dict[str, float] = {
        "total_return": total_return,
        "cagr": cagr,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
        "win_rate": trade_metrics["win_rate"],
        "average_win": trade_metrics["average_win"],
        "average_loss": trade_metrics["average_loss"],
        "risk_reward_ratio": trade_metrics["risk_reward_ratio"],
        "expectancy": trade_metrics["expectancy"],
        "final_equity": float(equity.iloc[-1]) * scale,
    }
    return out


def _empty_summary(scale: float, base: float) -> dict[str, float]:
    z = 0.0
    return {
        "total_return": z,
        "cagr": z,
        "max_drawdown": z,
        "sharpe": z,
        "win_rate": z,
        "average_win": z,
        "average_loss": z,
        "risk_reward_ratio": z,
        "expectancy": z,
        "final_equity": base * scale,
    }


def _trade_metrics(trades_df: pd.DataFrame) -> dict[str, float]:
    if trades_df.empty or "return_pct" not in trades_df.columns:
        return {
            "win_rate": 0.0,
            "average_win": 0.0,
            "average_loss": 0.0,
            "risk_reward_ratio": 0.0,
            "expectancy": 0.0,
        }

    rets = pd.to_numeric(trades_df["return_pct"], errors="coerce").dropna()
    n = len(rets)
    if n == 0:
        return {
            "win_rate": 0.0,
            "average_win": 0.0,
            "average_loss": 0.0,
            "risk_reward_ratio": 0.0,
            "expectancy": 0.0,
        }

    wins = rets > 0
    losses = rets < 0
    win_count = int(wins.sum())
    loss_count = int(losses.sum())

    win_rate = win_count / n
    average_win = float(rets[wins].mean()) if win_count else 0.0
    average_loss = float(-rets[losses].mean()) if loss_count else 0.0

    if average_loss > 0:
        risk_reward_ratio = float(average_win / average_loss)
    elif average_win > 0:
        risk_reward_ratio = float("inf")
    else:
        risk_reward_ratio = 0.0

    expectancy = (win_rate * average_win) - ((1.0 - win_rate) * average_loss)

    return {
        "win_rate": float(win_rate),
        "average_win": average_win,
        "average_loss": average_loss,
        "risk_reward_ratio": risk_reward_ratio,
        "expectancy": float(expectancy),
    }
