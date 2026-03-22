"""Forecast snapshot orchestration."""

from datetime import datetime, timedelta, timezone
from typing import Dict, List

from weather.data.mapping import get_location
from weather.data.models.metar import get_metar
from weather.data.models.openmeteo import get_ecmwf, get_hrrr


def take_forecast_snapshot(city_slug: str, dates: List[str]) -> Dict[str, dict]:
    now_str = datetime.now(timezone.utc).isoformat()
    ecmwf = get_ecmwf(city_slug, dates)
    hrrr = get_hrrr(city_slug, dates)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    cutoff_hrrr = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%d")
    loc = get_location(city_slug)

    snapshots = {}
    for date in dates:
        snap = {
            "ts": now_str,
            "ecmwf": ecmwf.get(date),
            "hrrr": hrrr.get(date) if date <= cutoff_hrrr else None,
            "metar": get_metar(city_slug) if date == today else None,
        }
        if loc.region == "us" and snap["hrrr"] is not None:
            snap["best"] = snap["hrrr"]
            snap["best_source"] = "hrrr"
        elif snap["ecmwf"] is not None:
            snap["best"] = snap["ecmwf"]
            snap["best_source"] = "ecmwf"
        else:
            snap["best"] = None
            snap["best_source"] = None
        snapshots[date] = snap
    return snapshots

