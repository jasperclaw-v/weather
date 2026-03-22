"""Pure scanning helpers extracted from the legacy loop."""

import json
from typing import Dict, List, Optional

from weather.core.finance import bet_size, calc_ev, calc_kelly
from weather.core.probability import bucket_probability, in_bucket
from weather.data.snapshots import take_forecast_snapshot
from weather.execution.polymarket import parse_temp_range


def build_outcomes(event: dict) -> List[dict]:
    outcomes = []
    for market in event.get("markets", []):
        question = market.get("question", "")
        market_id = str(market.get("id", ""))
        volume = float(market.get("volume", 0))
        bucket_range = parse_temp_range(question)
        if not bucket_range:
            continue
        try:
            prices = json.loads(market.get("outcomePrices", "[0.5,0.5]"))
            bid = float(prices[0])
            ask = float(prices[1]) if len(prices) > 1 else bid
        except Exception:
            continue
        outcomes.append(
            {
                "question": question,
                "market_id": market_id,
                "range": bucket_range,
                "bid": round(bid, 4),
                "ask": round(ask, 4),
                "price": round(bid, 4),
                "spread": round(ask - bid, 4),
                "volume": round(volume, 0),
            }
        )
    outcomes.sort(key=lambda item: item["range"][0])
    return outcomes


def select_signal(
    outcomes: List[dict],
    forecast_temp: float,
    sigma: float,
    best_source: str,
    opened_at: str,
    balance: float,
    min_volume: float,
    min_ev: float,
    kelly_fraction: float,
    max_bet: float,
    min_size: float = 0.5,
) -> Optional[dict]:
    matched_bucket = None
    for outcome in outcomes:
        low, high = outcome["range"]
        if in_bucket(forecast_temp, low, high):
            matched_bucket = outcome
            break

    if matched_bucket is None:
        return None

    low, high = matched_bucket["range"]
    volume = matched_bucket["volume"]
    bid = matched_bucket.get("bid", matched_bucket["price"])
    ask = matched_bucket.get("ask", matched_bucket["price"])
    spread = matched_bucket.get("spread", 0.0)

    if volume < min_volume:
        return None

    probability = bucket_probability(forecast_temp, low, high, sigma)
    ev = calc_ev(probability, ask)
    if ev < min_ev:
        return None

    kelly = calc_kelly(probability, ask, fraction=kelly_fraction)
    size = bet_size(kelly, balance, max_bet=max_bet)
    if size < min_size:
        return None

    return {
        "market_id": matched_bucket["market_id"],
        "question": matched_bucket["question"],
        "bucket_low": low,
        "bucket_high": high,
        "entry_price": ask,
        "bid_at_entry": bid,
        "spread": spread,
        "shares": round(size / ask, 2),
        "cost": size,
        "p": round(probability, 4),
        "ev": round(ev, 4),
        "kelly": round(kelly, 4),
        "forecast_temp": forecast_temp,
        "forecast_src": best_source,
        "sigma": sigma,
        "opened_at": opened_at,
        "status": "open",
        "pnl": None,
        "exit_price": None,
        "close_reason": None,
        "closed_at": None,
    }


__all__ = ["build_outcomes", "select_signal", "take_forecast_snapshot"]
