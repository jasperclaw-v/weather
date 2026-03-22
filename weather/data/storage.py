"""JSON persistence helpers."""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

DATA_DIR = Path("data")
STATE_FILE = DATA_DIR / "state.json"
MARKETS_DIR = DATA_DIR / "markets"
CALIBRATION_FILE = DATA_DIR / "calibration.json"
TP_FILE = DATA_DIR / "tp_schedule.json"


def ensure_dirs() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    MARKETS_DIR.mkdir(exist_ok=True)


def market_path(city_slug: str, date_str: str) -> Path:
    ensure_dirs()
    return MARKETS_DIR / f"{city_slug}_{date_str}.json"


def load_market(city_slug: str, date_str: str) -> Optional[Dict[str, Any]]:
    path = market_path(city_slug, date_str)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def save_market(market: Dict[str, Any]) -> None:
    path = market_path(market["city"], market["date"])
    path.write_text(json.dumps(market, indent=2, ensure_ascii=False), encoding="utf-8")


def load_all_markets() -> List[Dict[str, Any]]:
    ensure_dirs()
    markets = []
    for path in MARKETS_DIR.glob("*.json"):
        try:
            markets.append(json.loads(path.read_text(encoding="utf-8")))
        except Exception:
            continue
    return markets


def load_state(default_balance: float = 10000.0) -> Dict[str, Any]:
    ensure_dirs()
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    return {
        "balance": default_balance,
        "starting_balance": default_balance,
        "total_trades": 0,
        "wins": 0,
        "losses": 0,
        "peak_balance": default_balance,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def save_state(state: Dict[str, Any]) -> None:
    ensure_dirs()
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def new_market_record(city_slug: str, loc: Dict[str, Any], date_str: str, event: Dict[str, Any], hours: float) -> Dict[str, Any]:
    return {
        "city": city_slug,
        "city_name": loc["name"],
        "date": date_str,
        "unit": loc["unit"],
        "station": loc["station"],
        "event_end_date": event.get("endDate", ""),
        "hours_at_discovery": round(hours, 1),
        "status": "open",
        "position": None,
        "actual_temp": None,
        "resolved_outcome": None,
        "pnl": None,
        "forecast_snapshots": [],
        "market_snapshots": [],
        "all_outcomes": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
