"""Position lifecycle helpers extracted from the legacy runner."""

from datetime import datetime, timezone
from typing import Optional, Tuple

import requests

from weather.core.finance import calc_ev
from weather.core.probability import in_bucket
from weather.strategy.risk import get_tp_threshold


def find_outcome_price(outcomes: list[dict], market_id: str, side: str = "bid") -> Optional[float]:
    for outcome in outcomes:
        if outcome["market_id"] == market_id:
            return outcome.get(side, outcome.get("price"))
    return None


def apply_stop_and_forecast_exits(
    market: dict,
    outcomes: list[dict],
    forecast_temp: Optional[float],
    balance: float,
    ts: str,
) -> Tuple[dict, float, int, Optional[str]]:
    position = market.get("position")
    if not position or position.get("status") != "open":
        return market, balance, 0, None

    current_price = find_outcome_price(outcomes, position["market_id"], side="bid")
    if current_price is None:
        return market, balance, 0, None

    entry = position["entry_price"]
    stop = position.get("stop_price", entry * 0.80)

    if current_price >= entry * 1.20 and stop < entry:
        position["stop_price"] = entry
        position["trailing_activated"] = True
        stop = entry

    if current_price <= stop:
        pnl = round((current_price - entry) * position["shares"], 2)
        balance += position["cost"] + pnl
        position["closed_at"] = ts
        position["close_reason"] = "stop_loss" if current_price < entry else "trailing_stop"
        position["exit_price"] = current_price
        position["pnl"] = pnl
        position["status"] = "closed"
        reason = "STOP" if current_price < entry else "TRAILING BE"
        return market, balance, 1, reason

    if forecast_temp is not None:
        low = position["bucket_low"]
        high = position["bucket_high"]
        unit = market["unit"]
        buffer_value = 2.0 if unit == "F" else 1.0
        mid_bucket = (low + high) / 2 if low != -999 and high != 999 else forecast_temp
        forecast_far = abs(forecast_temp - mid_bucket) > (abs(mid_bucket - low) + buffer_value)
        if not in_bucket(forecast_temp, low, high) and forecast_far:
            pnl = round((current_price - position["entry_price"]) * position["shares"], 2)
            balance += position["cost"] + pnl
            position["closed_at"] = ts
            position["close_reason"] = "forecast_changed"
            position["exit_price"] = current_price
            position["pnl"] = pnl
            position["status"] = "closed"
            return market, balance, 1, "CLOSE"

    return market, balance, 0, None


def refresh_signal_with_live_quotes(
    signal: dict,
    max_slippage: float,
    max_price: float,
) -> Tuple[Optional[dict], Optional[str]]:
    try:
        response = requests.get(
            f"https://gamma-api.polymarket.com/markets/{signal['market_id']}",
            timeout=(3, 5),
        )
        response.raise_for_status()
        data = response.json()
        real_ask = float(data.get("bestAsk", signal["entry_price"]))
        real_bid = float(data.get("bestBid", signal["bid_at_entry"]))
    except Exception as exc:
        return signal, f"warn:{exc}"

    real_spread = round(real_ask - real_bid, 4)
    if real_spread > max_slippage or real_ask >= max_price:
        return None, f"skip:{real_ask:.3f}:{real_spread:.3f}"

    signal["entry_price"] = real_ask
    signal["bid_at_entry"] = real_bid
    signal["spread"] = real_spread
    signal["shares"] = round(signal["cost"] / real_ask, 2)
    signal["ev"] = round(calc_ev(signal["p"], real_ask), 4)
    return signal, None


def apply_resolution(market: dict, won: bool, ts: Optional[str] = None) -> Tuple[dict, float, str]:
    position = market["position"]
    price = position["entry_price"]
    size = position["cost"]
    shares = position["shares"]
    pnl = round(shares * (1 - price), 2) if won else round(-size, 2)
    timestamp = ts or datetime.now(timezone.utc).isoformat()

    position["exit_price"] = 1.0 if won else 0.0
    position["pnl"] = pnl
    position["close_reason"] = "resolved"
    position["closed_at"] = timestamp
    position["status"] = "closed"
    market["pnl"] = pnl
    market["status"] = "resolved"
    market["resolved_outcome"] = "win" if won else "loss"
    return market, size + pnl, market["resolved_outcome"]


def apply_monitor_exit(
    market: dict,
    current_price: float,
    hours_left: float,
    schedule: list[dict],
) -> Tuple[dict, int, Optional[str]]:
    position = market["position"]
    entry = position["entry_price"]
    stop = position.get("stop_price", entry * 0.80)
    take_profit = get_tp_threshold(hours_left, schedule)

    if current_price >= entry * 1.20 and stop < entry:
        position["stop_price"] = entry
        position["trailing_activated"] = True
        stop = entry

    take_triggered = take_profit is not None and current_price >= take_profit
    stop_triggered = current_price <= stop
    if not take_triggered and not stop_triggered:
        return market, 0, None

    pnl = round((current_price - entry) * position["shares"], 2)
    position["closed_at"] = datetime.now(timezone.utc).isoformat()
    if take_triggered:
        position["close_reason"] = "take_profit"
        reason = "TAKE"
    elif current_price < entry:
        position["close_reason"] = "stop_loss"
        reason = "STOP"
    else:
        position["close_reason"] = "trailing_stop"
        reason = "TRAILING BE"
    position["exit_price"] = current_price
    position["pnl"] = pnl
    position["status"] = "closed"
    return market, 1, reason
