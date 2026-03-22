"""Open-Meteo forecast adapters."""

import time
from typing import Dict, List, Optional

import requests

from weather.data.mapping import TIMEZONES, get_location

_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "weather/0.1"})


def _get_json(url: str, timeout=(5, 10)) -> Optional[dict]:
    for attempt in range(3):
        try:
            response = _SESSION.get(url, timeout=timeout)
            response.raise_for_status()
            return response.json()
        except Exception:
            if attempt < 2:
                time.sleep(3)
    return None


def get_ecmwf(city_slug: str, dates: List[str]) -> Dict[str, float]:
    loc = get_location(city_slug)
    temp_unit = "fahrenheit" if loc.unit == "F" else "celsius"
    tz = TIMEZONES.get(city_slug, "UTC")
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={loc.lat}&longitude={loc.lon}"
        f"&daily=temperature_2m_max&temperature_unit={temp_unit}"
        f"&forecast_days=7&timezone={tz}"
        "&models=ecmwf_ifs025&bias_correction=true"
    )
    data = _get_json(url)
    if not data or "error" in data:
        return {}
    result = {}
    for date, temp in zip(data["daily"]["time"], data["daily"]["temperature_2m_max"]):
        if date in dates and temp is not None:
            result[date] = round(temp, 1) if loc.unit == "C" else round(temp)
    return result


def get_hrrr(city_slug: str, dates: List[str]) -> Dict[str, float]:
    """Compatibility adapter for the existing US short-range source."""
    loc = get_location(city_slug)
    if loc.region != "us":
        return {}
    tz = TIMEZONES.get(city_slug, "UTC")
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={loc.lat}&longitude={loc.lon}"
        "&daily=temperature_2m_max&temperature_unit=fahrenheit"
        f"&forecast_days=3&timezone={tz}"
        "&models=gfs_seamless"
    )
    data = _get_json(url)
    if not data or "error" in data:
        return {}
    result = {}
    for date, temp in zip(data["daily"]["time"], data["daily"]["temperature_2m_max"]):
        if date in dates and temp is not None:
            result[date] = round(temp)
    return result

