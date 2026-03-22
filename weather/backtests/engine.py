"""Event-driven replay over persisted market records."""

from typing import Dict, List, Optional

from weather.backtests.loaders import load_replay_markets
from weather.backtests.metrics import brier_score, max_drawdown, sharpe_ratio, sortino_ratio, win_rate


def _extract_trade_record(market: dict) -> Optional[dict]:
    position = market.get("position")
    if not position:
        return None
    pnl = market.get("pnl")
    if pnl is None:
        pnl = position.get("pnl")
    if pnl is None:
        return None
    probability = position.get("p")
    resolved = market.get("resolved_outcome")
    outcome = 1 if resolved == "win" else 0 if resolved == "loss" else None
    return {
        "market_id": position.get("market_id"),
        "city": market.get("city"),
        "date": market.get("date"),
        "probability": probability,
        "outcome": outcome,
        "pnl": float(pnl),
        "close_reason": position.get("close_reason"),
    }


def replay_markets(markets: List[dict]) -> Dict[str, object]:
    trades = []
    for market in markets:
        trade = _extract_trade_record(market)
        if trade is not None:
            trades.append(trade)

    pnls = [trade["pnl"] for trade in trades]
    resolved_probs = [trade["probability"] for trade in trades if trade["probability"] is not None and trade["outcome"] is not None]
    resolved_outcomes = [trade["outcome"] for trade in trades if trade["probability"] is not None and trade["outcome"] is not None]

    summary = {
        "n_trades": len(trades),
        "total_pnl": round(sum(pnls), 2),
        "max_drawdown": max_drawdown(pnls),
        "sharpe": sharpe_ratio(pnls),
        "sortino": sortino_ratio(pnls),
        "brier": brier_score(resolved_probs, resolved_outcomes) if resolved_probs else 0.0,
        "win_rate": win_rate(resolved_outcomes) if resolved_outcomes else 0.0,
        "trades": trades,
    }
    return summary


def replay_from_storage(city: Optional[str] = None) -> Dict[str, object]:
    return replay_markets(load_replay_markets(city=city))
