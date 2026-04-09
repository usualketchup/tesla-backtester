from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from tesla_bt.engine import run_backtest
from tesla_bt.indicators import add_vwap
from tesla_bt.metrics import summarize_backtest
from tesla_bt.strategies.buy_hold import buy_hold
from tesla_bt.strategies.protocols import Strategy


@dataclass
class StrategyRunArtifacts:
    metrics: pd.DataFrame
    trades: dict[str, pd.DataFrame]
    equity_curves: dict[str, pd.Series]


def _run_strategy_suite(
    df: pd.DataFrame,
    strategies: dict[str, Strategy],
    *,
    initial_capital: float = 100_000.0,
    commission_rate: float = 0.0,
) -> StrategyRunArtifacts:
    strategies_with_benchmark = dict(strategies)
    strategies_with_benchmark["buy_and_hold"] = buy_hold

    frame = add_vwap(df)
    open_ = frame["Open"]
    close = frame["Close"]

    rows: list[dict[str, float | str]] = []
    trades_by_strategy: dict[str, pd.DataFrame] = {}
    equity_by_strategy: dict[str, pd.Series] = {}

    for name, fn in strategies_with_benchmark.items():
        entry_signal, exit_signal = fn(frame)
        result = run_backtest(
            open_,
            close,
            entry_signal,
            exit_signal,
            commission_rate=commission_rate,
        )
        metrics = summarize_backtest(
            result["trades"],
            result["equity_curve"],
            initial_capital=initial_capital,
        )
        metrics["strategy"] = name
        rows.append(metrics)
        trades_by_strategy[name] = result["trades"]
        equity_by_strategy[name] = result["equity_curve"]

    out = pd.DataFrame(rows).set_index("strategy")
    benchmark_return = float(out.loc["buy_and_hold", "total_return"])
    out["excess_return_vs_benchmark"] = out["total_return"] - benchmark_return
    out = out.sort_values(
        ["excess_return_vs_benchmark", "total_return"],
        ascending=[False, False],
    )

    return StrategyRunArtifacts(
        metrics=out,
        trades=trades_by_strategy,
        equity_curves=equity_by_strategy,
    )


def compare_strategies(
    df: pd.DataFrame,
    strategies: dict[str, Strategy],
    *,
    initial_capital: float = 100_000.0,
    commission_rate: float = 0.0,
) -> pd.DataFrame:
    """
    Run each strategy on the same OHLCV DataFrame and return a metrics table
    sorted by excess return versus a buy-and-hold benchmark (descending).

    Each strategy returns ``entry_signal`` and ``exit_signal`` as boolean
    ``pd.Series`` aligned with ``df.index``.

    A ``vwap`` column is added (see :func:`tesla_bt.indicators.add_vwap`) so
    strategies can use ``df["vwap"]`` without mutating the caller's frame.

    ``buy_and_hold`` is always included as the benchmark, and
    ``excess_return_vs_benchmark`` is computed as:
    ``strategy_total_return - buy_and_hold_total_return``.
    """
    return _run_strategy_suite(
        df,
        strategies,
        initial_capital=initial_capital,
        commission_rate=commission_rate,
    ).metrics


def compare_strategies_with_outputs(
    df: pd.DataFrame,
    strategies: dict[str, Strategy],
    *,
    initial_capital: float = 100_000.0,
    commission_rate: float = 0.0,
) -> StrategyRunArtifacts:
    """
    Run strategy comparison and return metrics plus per-strategy outputs.

    Returns:
        StrategyRunArtifacts with metrics DataFrame, and dicts mapping strategy
        names to trades DataFrames and equity curve Series.
    """
    return _run_strategy_suite(
        df,
        strategies,
        initial_capital=initial_capital,
        commission_rate=commission_rate,
    )
