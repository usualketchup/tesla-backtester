"""
Download TSLA history, run registered strategies, print a comparison table.

Usage:
  pip install -r requirements.txt
  python run_compare.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from tesla_bt.data import fetch_tsla
from tesla_bt.report import compare_strategies
from tesla_bt.strategies import buy_hold, rsi_threshold, sma_crossover


def main() -> None:
    start, end = "2022-01-01", "2026-01-01"
    cache = Path(__file__).resolve().parent / "data" / "tsla_daily.csv"
    df = fetch_tsla(start, end, cache_path=cache)

    strategies = {
        "buy_hold": buy_hold,
        "sma_20_50": lambda d: sma_crossover(d, 20, 50),
        "sma_50_200": lambda d: sma_crossover(d, 50, 200),
        "rsi_momentum_55": rsi_threshold,
    }

    table = compare_strategies(df, strategies, commission_rate=0.0)
    with pd.option_context("display.max_columns", None, "display.width", 120):
        print(table.to_string(float_format=lambda x: f"{x:,.4f}"))

    out = Path(__file__).resolve().parent / "reports"
    out.mkdir(exist_ok=True)
    csv_path = out / "strategy_comparison.csv"
    table.to_csv(csv_path)
    print(f"\nWrote {csv_path}")


if __name__ == "__main__":
    main()
