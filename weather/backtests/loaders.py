"""Load replay/backtest data from persisted market files."""

from typing import List, Optional

from weather.data.storage import load_all_markets


def load_replay_markets(city: Optional[str] = None) -> List[dict]:
    markets = load_all_markets()
    if city is not None:
        markets = [market for market in markets if market.get("city") == city]
    return markets

