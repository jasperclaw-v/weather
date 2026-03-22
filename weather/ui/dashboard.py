"""Streamlit dashboard for portfolio, replay metrics, and live paper scans."""

from __future__ import annotations

import re
import subprocess
import sys
from typing import Any, Dict, List
from pathlib import Path

from weather import runtime
from weather.backtests.engine import replay_from_storage
from weather.data.storage import load_all_markets
from weather.scan import run_paper_scan


BUY_RE = re.compile(
    r"\[BUY\]\s+(?P<city>.+?)\s+(?P<horizon>D\+\d+)\s+(?P<date>\d{4}-\d{2}-\d{2})\s+\|\s+"
    r"(?P<bucket>.+?)\s+\|\s+\$(?P<entry>[0-9.]+)\s+\|\s+EV\s+(?P<ev>[+-]?[0-9.]+)\s+\|\s+"
    r"\$(?P<cost>[0-9.]+)\s+\((?P<source>[^)]+)\)"
)
SKIP_RE = re.compile(
    r"\[SKIP\]\s+(?P<city>.+?)\s+(?P<date>\d{4}-\d{2}-\d{2})\s+[—-]\s+(?P<reason>.+)"
)
WARN_RE = re.compile(r"\[WARN\]\s+(?P<message>.+)")


def build_open_positions_rows(markets: List[dict]) -> List[dict]:
    rows = []
    for market in markets:
        position = market.get("position")
        if not position or position.get("status") != "open":
            continue
        rows.append(
            {
                "city": market["city_name"],
                "date": market["date"],
                "bucket": f"{position['bucket_low']}-{position['bucket_high']}{market['unit']}",
                "entry_price": position["entry_price"],
                "shares": position["shares"],
                "cost": position["cost"],
                "ev": position.get("ev"),
                "probability": position.get("p"),
                "source": position.get("forecast_src"),
            }
        )
    return rows


def build_resolved_rows(markets: List[dict]) -> List[dict]:
    rows = []
    for market in markets:
        if market.get("status") != "resolved" or market.get("pnl") is None:
            continue
        position = market.get("position") or {}
        rows.append(
            {
                "city": market["city_name"],
                "date": market["date"],
                "result": market.get("resolved_outcome"),
                "pnl": market.get("pnl"),
                "entry_price": position.get("entry_price"),
                "exit_price": position.get("exit_price"),
                "source": position.get("forecast_src"),
            }
        )
    return rows


def extract_scan_events(log_lines: List[str]) -> List[dict]:
    events = []
    for line in log_lines:
        cleaned = line.strip()
        buy = BUY_RE.search(cleaned)
        if buy:
            data = buy.groupdict()
            events.append(
                {
                    "type": "buy",
                    "city": data["city"],
                    "date": data["date"],
                    "detail": data["bucket"],
                    "entry_price": float(data["entry"]),
                    "ev": float(data["ev"]),
                    "cost": float(data["cost"]),
                    "source": data["source"].lower(),
                }
            )
            continue
        skip = SKIP_RE.search(cleaned)
        if skip:
            data = skip.groupdict()
            events.append(
                {
                    "type": "skip",
                    "city": data["city"],
                    "date": data["date"],
                    "detail": data["reason"],
                }
            )
            continue
        warn = WARN_RE.search(cleaned)
        if warn:
            events.append({"type": "warn", "city": None, "date": None, "detail": warn.group("message")})
    return events


def build_trade_history_rows(replay_summary: Dict[str, Any]) -> List[dict]:
    equity = 0.0
    rows = []
    for idx, trade in enumerate(replay_summary.get("trades", []), start=1):
        equity += float(trade["pnl"])
        rows.append(
            {
                "trade_number": idx,
                "city": trade.get("city"),
                "date": trade.get("date"),
                "pnl": trade.get("pnl"),
                "probability": trade.get("probability"),
                "outcome": trade.get("outcome"),
                "equity_pnl": round(equity, 2),
            }
        )
    return rows


def build_dashboard_snapshot(max_price: float | None = None, max_slippage: float | None = None) -> Dict[str, Any]:
    state = runtime.load_state()
    markets = load_all_markets()
    replay = replay_from_storage()
    scan = run_paper_scan(max_price=max_price, max_slippage=max_slippage)
    return {
        "state": state,
        "open_positions": build_open_positions_rows(markets),
        "resolved_markets": build_resolved_rows(markets),
        "replay": replay,
        "trade_history": build_trade_history_rows(replay),
        "scan": scan,
        "scan_events": extract_scan_events(scan.get("log", [])),
    }


def render_dashboard(max_price: float | None = None, max_slippage: float | None = None) -> None:
    try:
        import pandas as pd
        import plotly.express as px
        import streamlit as st
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Dashboard dependencies are not installed. Install with `python3 -m pip install -e '.[ui]'`."
        ) from exc

    snapshot = build_dashboard_snapshot(max_price=max_price, max_slippage=max_slippage)
    state = snapshot["state"]
    replay = snapshot["replay"]
    scan = snapshot["scan"]

    st.set_page_config(page_title="Weather Dashboard", layout="wide")
    st.title("Weather Dashboard")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Balance", f"${state['balance']:,.2f}")
    col2.metric("Open Positions", str(len(snapshot["open_positions"])))
    col3.metric("Resolved Trades", str(replay["n_trades"]))
    col4.metric("Total PnL", f"${replay['total_pnl']:,.2f}")

    col5, col6, col7, col8 = st.columns(4)
    col5.metric("Win Rate", f"{replay['win_rate']:.1%}")
    col6.metric("Brier", f"{replay['brier']:.4f}")
    col7.metric("Sharpe", f"{replay['sharpe']:.3f}")
    col8.metric("Max Drawdown", f"${replay['max_drawdown']:,.2f}")

    st.subheader("Live Paper Scan")
    st.json(
        {
            "filters": scan["filters"],
            "scan_result": scan["scan_result"],
        },
        expanded=False,
    )

    if snapshot["scan_events"]:
        st.dataframe(pd.DataFrame(snapshot["scan_events"]), use_container_width=True)
    if scan["positions"]:
        st.subheader("Would-Buy Positions")
        st.dataframe(pd.DataFrame(scan["positions"]), use_container_width=True)

    st.subheader("Current Open Positions")
    if snapshot["open_positions"]:
        st.dataframe(pd.DataFrame(snapshot["open_positions"]), use_container_width=True)
    else:
        st.write("No open positions.")

    st.subheader("Resolved Market History")
    if snapshot["resolved_markets"]:
        st.dataframe(pd.DataFrame(snapshot["resolved_markets"]), use_container_width=True)
    else:
        st.write("No resolved markets yet.")

    st.subheader("Replay Equity Curve")
    history_rows = snapshot["trade_history"]
    if history_rows:
        history_df = pd.DataFrame(history_rows)
        fig = px.line(history_df, x="trade_number", y="equity_pnl", markers=True)
        fig.update_layout(xaxis_title="Trade Number", yaxis_title="Cumulative PnL")
        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(history_df, use_container_width=True)
    else:
        st.write("No resolved trade history yet.")


def main() -> None:  # pragma: no cover
    render_dashboard(
        max_price=runtime.CONFIG.max_price,
        max_slippage=runtime.CONFIG.max_slippage,
    )


def launch_dashboard() -> int:
    dashboard_path = Path(__file__).resolve()
    return subprocess.call([sys.executable, "-m", "streamlit", "run", str(dashboard_path)])


if __name__ == "__main__":  # pragma: no cover
    main()
