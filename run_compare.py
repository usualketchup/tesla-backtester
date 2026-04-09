"""
Download TSLA history, run registered strategies, print a comparison table.

Usage:
  pip install -r requirements.txt
  python run_compare.py
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd

from tesla_bt.data import fetch_tsla
from tesla_bt.report import compare_strategies_with_outputs
from tesla_bt.strategies import rsi_threshold, sma_crossover


def main() -> None:
    start, end = "2022-01-01", "2026-01-01"
    cache = Path(__file__).resolve().parent / "data" / "tsla_daily.csv"
    df = fetch_tsla(start, end, cache_path=cache)

    strategies = {
        "sma_20_50": lambda d: sma_crossover(d, 20, 50),
        "sma_50_200": lambda d: sma_crossover(d, 50, 200),
        "rsi_55_50": rsi_threshold,
    }

    artifacts = compare_strategies_with_outputs(df, strategies, commission_rate=0.0)
    table = artifacts.metrics
    with pd.option_context("display.max_columns", None, "display.width", 120):
        print(table.to_string(float_format=lambda x: f"{x:,.4f}"))

    reports_root = Path(__file__).resolve().parent / "reports"
    run_dir = reports_root / datetime.now().strftime("%Y-%m-%d_%H-%M")
    run_dir.mkdir(parents=True, exist_ok=True)

    metrics_path = run_dir / "metrics.csv"
    table.to_csv(metrics_path)

    for strategy_name, trades_df in artifacts.trades.items():
        trades_path = run_dir / f"trades_{strategy_name}.csv"
        trades_df.to_csv(trades_path, index=False)

    for strategy_name, equity_curve in artifacts.equity_curves.items():
        equity_path = run_dir / f"equity_curve_{strategy_name}.csv"
        equity_curve.rename("equity").to_csv(equity_path, header=True)

    print(f"\nWrote report outputs to {run_dir}")


if __name__ == "__main__":
    main()
