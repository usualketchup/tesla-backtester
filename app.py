from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from tesla_bt.data import fetch_tsla
from tesla_bt.engine import run_backtest
from tesla_bt.metrics import summarize_backtest
from tesla_bt.strategies import buy_hold, rsi_threshold, sma_crossover


STRATEGY_OPTIONS = ("buy_and_hold", "sma_crossover", "rsi_threshold")


def _render_sidebar() -> dict[str, object]:
    st.sidebar.header("Configuration")

    app_mode = st.sidebar.radio("Mode", ("Single Strategy", "Compare Strategies"), index=0)
    strategy_name = st.sidebar.selectbox("Strategy", STRATEGY_OPTIONS, index=1)
    compare_strategies = st.sidebar.multiselect(
        "Strategies to compare",
        STRATEGY_OPTIONS,
        default=["buy_and_hold", "sma_crossover", "rsi_threshold"],
    )

    sma_fast = st.sidebar.number_input("SMA fast", min_value=2, max_value=400, value=20, step=1)
    sma_slow = st.sidebar.number_input("SMA slow", min_value=3, max_value=500, value=50, step=1)
    if sma_fast >= sma_slow:
        st.sidebar.warning("For SMA crossover, keep fast < slow.")

    rsi_entry = st.sidebar.number_input("RSI entry", min_value=1.0, max_value=99.0, value=55.0, step=1.0)
    rsi_exit = st.sidebar.number_input("RSI exit", min_value=1.0, max_value=99.0, value=50.0, step=1.0)

    stop_loss_pct = st.sidebar.number_input(
        "stop_loss_pct", min_value=0.0, max_value=1.0, value=0.0, step=0.005, format="%.3f"
    )
    take_profit_pct = st.sidebar.number_input(
        "take_profit_pct", min_value=0.0, max_value=2.0, value=0.0, step=0.01, format="%.3f"
    )
    slippage_pct = st.sidebar.number_input(
        "slippage_pct", min_value=0.0, max_value=0.1, value=0.001, step=0.0005, format="%.4f"
    )

    default_end = date.today()
    default_start = default_end - timedelta(days=365 * 3)
    start_date = st.sidebar.date_input("Start date", value=default_start)
    end_date = st.sidebar.date_input("End date", value=default_end)

    return {
        "app_mode": app_mode,
        "strategy_name": strategy_name,
        "compare_strategies": list(compare_strategies),
        "sma_fast": int(sma_fast),
        "sma_slow": int(sma_slow),
        "rsi_entry": float(rsi_entry),
        "rsi_exit": float(rsi_exit),
        "stop_loss_pct": float(stop_loss_pct),
        "take_profit_pct": float(take_profit_pct),
        "slippage_pct": float(slippage_pct),
        "start_date": start_date,
        "end_date": end_date,
    }


def _build_strategy_signals(
    strategy_name: str,
    df: pd.DataFrame,
    config: dict[str, object],
) -> tuple[pd.Series, pd.Series]:
    if strategy_name == "buy_and_hold":
        return buy_hold(df)
    if strategy_name == "sma_crossover":
        return sma_crossover(
            df,
            fast=int(config["sma_fast"]),
            slow=int(config["sma_slow"]),
        )
    if strategy_name == "rsi_threshold":
        return rsi_threshold(
            df,
            entry_level=float(config["rsi_entry"]),
            exit_level=float(config["rsi_exit"]),
        )
    raise ValueError(f"Unsupported strategy: {strategy_name}")


def _load_data_from_config(config: dict[str, object]) -> pd.DataFrame:
    start_date = config["start_date"]
    end_date = config["end_date"]
    if not isinstance(start_date, date) or not isinstance(end_date, date):
        raise ValueError("Invalid date selection.")
    if start_date >= end_date:
        raise ValueError("Start date must be earlier than end date.")

    # yfinance end date is exclusive; include selected end date by adding one day.
    df = fetch_tsla(start=start_date.isoformat(), end=(end_date + timedelta(days=1)).isoformat())
    if df.empty:
        raise ValueError("No data returned for selected range.")
    return df


def _run_backtest_for_strategy(
    strategy_name: str,
    df: pd.DataFrame,
    config: dict[str, object],
) -> tuple[dict[str, float], pd.Series, pd.DataFrame]:
    entry_signal, exit_signal = _build_strategy_signals(strategy_name, df, config)

    stop_loss_pct = float(config["stop_loss_pct"])
    take_profit_pct = float(config["take_profit_pct"])
    result = run_backtest(
        open_=df["Open"],
        close=df["Close"],
        entry_signal=entry_signal,
        exit_signal=exit_signal,
        high=df["High"],
        low=df["Low"],
        stop_loss_pct=stop_loss_pct if stop_loss_pct > 0 else None,
        take_profit_pct=take_profit_pct if take_profit_pct > 0 else None,
        slippage_pct=float(config["slippage_pct"]),
    )

    metrics = summarize_backtest(result["trades"], result["equity_curve"])
    return metrics, result["equity_curve"], result["trades"]


def _run_backtest_from_config(
    config: dict[str, object],
) -> tuple[dict[str, float], pd.Series, pd.DataFrame, pd.Series]:
    df = _load_data_from_config(config)
    strategy_name = str(config["strategy_name"])
    metrics, equity_curve, trades_df = _run_backtest_for_strategy(strategy_name, df, config)
    return metrics, equity_curve, trades_df, df["Close"]


def _run_comparison_from_config(
    config: dict[str, object],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    strategy_names = [str(name) for name in config.get("compare_strategies", [])]
    if not strategy_names:
        raise ValueError("Select at least one strategy to compare.")

    df = _load_data_from_config(config)
    metrics_rows: list[dict[str, float | str]] = []
    eq_frame = pd.DataFrame(index=df.index)

    for strategy_name in strategy_names:
        metrics, equity_curve, _ = _run_backtest_for_strategy(strategy_name, df, config)
        metrics_rows.append({"strategy": strategy_name, **metrics})
        eq_frame[strategy_name] = equity_curve.reindex(df.index).astype(float)

    metrics_df = pd.DataFrame(metrics_rows).set_index("strategy")
    if "total_return" in metrics_df.columns:
        metrics_df = metrics_df.sort_values("total_return", ascending=False)
    return metrics_df, eq_frame


def _render_comparison_results(metrics_df: pd.DataFrame, eq_frame: pd.DataFrame) -> None:
    st.subheader("Strategy Comparison Metrics")
    st.dataframe(metrics_df, use_container_width=True)

    st.subheader("Equity Curves Comparison")
    eq_long = eq_frame.rename_axis("timestamp").reset_index().melt(
        id_vars="timestamp",
        var_name="strategy",
        value_name="equity",
    )
    eq_fig = px.line(
        eq_long,
        x="timestamp",
        y="equity",
        color="strategy",
        title="Overlaid Equity Curves",
    )
    st.plotly_chart(eq_fig, use_container_width=True)


def _build_drawdown_series(equity_curve: pd.Series) -> pd.Series:
    if equity_curve.empty:
        return pd.Series(dtype=float, name="drawdown")
    running_peak = equity_curve.cummax()
    drawdown = (equity_curve / running_peak) - 1.0
    return drawdown.rename("drawdown")


def _build_price_with_trades_chart(close: pd.Series, trades_df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=close.index,
            y=close.values,
            mode="lines",
            name="Close",
            line={"width": 2},
        )
    )

    if not trades_df.empty:
        fig.add_trace(
            go.Scatter(
                x=trades_df["entry_time"],
                y=trades_df["entry_price"],
                mode="markers",
                name="Entry",
                marker={"symbol": "triangle-up", "size": 10},
                hovertemplate="Entry<br>%{x}<br>Price: %{y:.2f}<extra></extra>",
            )
        )
        fig.add_trace(
            go.Scatter(
                x=trades_df["exit_time"],
                y=trades_df["exit_price"],
                mode="markers",
                name="Exit",
                marker={"symbol": "triangle-down", "size": 10},
                hovertemplate="Exit<br>%{x}<br>Price: %{y:.2f}<extra></extra>",
            )
        )

    fig.update_layout(title="Price Chart with Entry/Exit Markers", xaxis_title="Time", yaxis_title="Price")
    return fig


def _render_results(
    metrics: dict[str, float],
    equity_curve: pd.Series,
    trades_df: pd.DataFrame,
    close: pd.Series,
) -> None:
    st.subheader("Metrics")
    metrics_df = pd.DataFrame([metrics]).T.rename(columns={0: "value"})
    st.dataframe(metrics_df, use_container_width=True)

    st.subheader("Equity Curve")
    eq_df = equity_curve.rename("equity").reset_index()
    eq_df.columns = ["timestamp", "equity"]
    eq_fig = px.line(eq_df, x="timestamp", y="equity", title="Equity Curve")
    st.plotly_chart(eq_fig, use_container_width=True)

    st.subheader("Drawdown")
    dd_df = _build_drawdown_series(equity_curve).reset_index()
    dd_df.columns = ["timestamp", "drawdown"]
    dd_fig = px.line(dd_df, x="timestamp", y="drawdown", title="Drawdown")
    dd_fig.update_yaxes(tickformat=".1%")
    st.plotly_chart(dd_fig, use_container_width=True)

    st.subheader("Price with Trades")
    st.plotly_chart(_build_price_with_trades_chart(close, trades_df), use_container_width=True)

    st.subheader("Trades Table")
    st.dataframe(trades_df, use_container_width=True)

    st.subheader("Histogram of Trade Returns")
    trade_returns = pd.to_numeric(trades_df.get("return_pct"), errors="coerce").dropna()
    if trade_returns.empty:
        st.info("No closed trade returns to display.")
    else:
        hist_fig = px.histogram(
            trade_returns.reset_index(drop=True).to_frame(name="trade_return"),
            x="trade_return",
            nbins=40,
            title="Distribution of Trade Returns",
        )
        hist_fig.update_xaxes(tickformat=".1%")
        st.plotly_chart(hist_fig, use_container_width=True)


def main() -> None:
    st.set_page_config(page_title="Backtesting Engine", layout="wide")
    st.title("Backtesting Engine")

    config = _render_sidebar()
    app_mode = str(config["app_mode"])
    run_label = "Run Comparison" if app_mode == "Compare Strategies" else "Run Backtest"
    run_clicked = st.button(run_label, type="primary")

    if not run_clicked:
        st.info("Select settings in the sidebar, then click the run button.")
        return

    try:
        with st.spinner("Running backtest..."):
            if app_mode == "Compare Strategies":
                metrics_df, eq_frame = _run_comparison_from_config(config)
            else:
                metrics, equity_curve, trades_df, close = _run_backtest_from_config(config)
        if app_mode == "Compare Strategies":
            _render_comparison_results(metrics_df, eq_frame)
        else:
            _render_results(metrics, equity_curve, trades_df, close)
    except Exception as exc:
        st.error(f"Backtest failed: {exc}")


if __name__ == "__main__":
    main()
