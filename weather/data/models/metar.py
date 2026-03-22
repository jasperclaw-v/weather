"""METAR observation adapter."""

from typing import Optional

import requests

from weather.data.mapping import get_location


def get_metar(city_slug: str) -> Optional[float]:
    loc = get_location(city_slug)
    url = f"https://aviationweather.gov/api/data/metar?ids={loc.station}&format=json"
    try:
        response = requests.get(url, timeout=(5, 8))
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None
    if not data or not isinstance(data, list):
        return None
    temp_c = data[0].get("temp")
    if temp_c is None:
        return None
    if loc.unit == "F":
        return round(float(temp_c) * 9 / 5 + 32)
    return round(float(temp_c), 1)

