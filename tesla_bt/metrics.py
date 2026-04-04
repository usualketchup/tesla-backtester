from __future__ import annotations

import numpy as np
import pandas as pd

TRADING_DAYS = 252


def _max_drawdown(equity: pd.Series) -> float:
    peak = equity.cummax()
    dd = (equity / peak) - 1.0
    return float(dd.min())


def summarize_backtest(
    result: dict[str, pd.DataFrame | pd.Series],
    *,
    initial_capital: float = 100_000.0,
) -> dict[str, float]:
    """
    Summary stats from `run_backtest` output (keys: equity_curve, returns).

    Scales ``final_equity`` by ``initial_capital`` relative to the curve's
    starting value (typically 1.0).
    """
    equity = result["equity_curve"]
    strat_ret = result["returns"].dropna()
    if equity.empty or strat_ret.empty:
        base = float(equity.iloc[0]) if len(equity) else 1.0
        end_eq = float(equity.iloc[-1]) if len(equity) else base
        scale = initial_capital / base if base else initial_capital
        return {
            "total_return": 0.0,
            "cagr": 0.0,
            "volatility": 0.0,
            "sharpe": 0.0,
            "max_drawdown": 0.0,
            "final_equity": end_eq * scale,
        }

    base = float(equity.iloc[0])
    scale = initial_capital / base if base else initial_capital
    total_return = float(equity.iloc[-1] / equity.iloc[0] - 1.0)
    n = len(strat_ret)
    years = n / TRADING_DAYS
    cagr = (
        float((equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1.0) if years > 0 else 0.0
    )
    if len(strat_ret) < 2:
        ann_vol = 0.0
        sharpe = 0.0
    else:
        daily_vol = float(strat_ret.std(ddof=1))
        ann_vol = float(daily_vol * np.sqrt(TRADING_DAYS))
        mean_daily = float(strat_ret.mean())
        sharpe = float(
            (mean_daily / daily_vol) * np.sqrt(TRADING_DAYS) if daily_vol > 0 else 0.0
        )

    return {
        "total_return": total_return,
        "cagr": cagr,
        "volatility": ann_vol,
        "sharpe": sharpe,
        "max_drawdown": _max_drawdown(equity),
        "final_equity": float(equity.iloc[-1]) * scale,
    }
