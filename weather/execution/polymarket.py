"""Read-only Polymarket market helpers and parsing."""

import json
import re
from datetime import datetime, timezone
from typing import Optional, Tuple

import requests


def get_polymarket_event(city_slug: str, month: str, day: int, year: int) -> Optional[dict]:
    slug = f"highest-temperature-in-{city_slug}-on-{month}-{day}-{year}"
    try:
        response = requests.get(f"https://gamma-api.polymarket.com/events?slug={slug}", timeout=(5, 8))
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None
    if data and isinstance(data, list):
        return data[0]
    return None


def get_market_price(market_id: str) -> Optional[float]:
    try:
        response = requests.get(f"https://gamma-api.polymarket.com/markets/{market_id}", timeout=(3, 5))
        response.raise_for_status()
        prices = json.loads(response.json().get("outcomePrices", "[0.5,0.5]"))
        return float(prices[0])
    except Exception:
        return None


def check_market_resolved(market_id: str) -> Optional[bool]:
    try:
        response = requests.get(f"https://gamma-api.polymarket.com/markets/{market_id}", timeout=(5, 8))
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None
    if not data.get("closed", False):
        return None
    try:
        prices = json.loads(data.get("outcomePrices", "[0.5,0.5]"))
        yes_price = float(prices[0])
    except Exception:
        return None
    if yes_price >= 0.95:
        return True
    if yes_price <= 0.05:
        return False
    return None


def parse_temp_range(question: str) -> Optional[Tuple[float, float]]:
    if not question:
        return None
    num = r"(-?\d+(?:\.\d+)?)"
    if re.search(r"or below", question, re.IGNORECASE):
        match = re.search(num + r"[°]?[FC] or below", question, re.IGNORECASE)
        if match:
            return (-999.0, float(match.group(1)))
    if re.search(r"or higher", question, re.IGNORECASE):
        match = re.search(num + r"[°]?[FC] or higher", question, re.IGNORECASE)
        if match:
            return (float(match.group(1)), 999.0)
    match = re.search(r"between " + num + r"-" + num + r"[°]?[FC]", question, re.IGNORECASE)
    if match:
        return (float(match.group(1)), float(match.group(2)))
    match = re.search(r"be " + num + r"[°]?[FC] on", question, re.IGNORECASE)
    if match:
        value = float(match.group(1))
        return (value, value)
    return None


def hours_to_resolution(end_date_str: str) -> float:
    try:
        end = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        return max(0.0, (end - datetime.now(timezone.utc)).total_seconds() / 3600)
    except Exception:
        return 999.0

