"""Visual Crossing actual-temperature adapter."""

import os
from typing import Optional

import requests

from weather.data.mapping import get_location


def get_actual_temp(city_slug: str, date_str: str, api_key: Optional[str] = None) -> Optional[float]:
    key = api_key or os.getenv("VC_KEY", "")
    if not key:
        return None
    loc = get_location(city_slug)
    unit_group = "us" if loc.unit == "F" else "metric"
    url = (
        "https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline"
        f"/{loc.station}/{date_str}/{date_str}"
        f"?unitGroup={unit_group}&key={key}&include=days&elements=tempmax"
    )
    try:
        response = requests.get(url, timeout=(5, 8))
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None
    days = data.get("days", [])
    if days and days[0].get("tempmax") is not None:
        return round(float(days[0]["tempmax"]), 1)
    return None

