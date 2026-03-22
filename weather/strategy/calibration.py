"""Forecast error calibration helpers."""

import json
from datetime import datetime, timezone
from statistics import pstdev
from typing import Dict, List, Optional

from weather.core.constants import DEFAULT_SIGMA_C, DEFAULT_SIGMA_F
from weather.data.mapping import LOCATIONS
from weather.data.storage import CALIBRATION_FILE, ensure_dirs


def load_calibration() -> Dict[str, dict]:
    ensure_dirs()
    if CALIBRATION_FILE.exists():
        return json.loads(CALIBRATION_FILE.read_text(encoding="utf-8"))
    return {}


def save_calibration(calibration: Dict[str, dict]) -> None:
    ensure_dirs()
    CALIBRATION_FILE.write_text(json.dumps(calibration, indent=2), encoding="utf-8")


def default_sigma_for_city(city_slug: str) -> float:
    return DEFAULT_SIGMA_F if LOCATIONS[city_slug].unit == "F" else DEFAULT_SIGMA_C


def get_sigma(city_slug: str, source: str = "ecmwf", calibration: Optional[Dict[str, dict]] = None) -> float:
    calibration = calibration if calibration is not None else load_calibration()
    key = f"{city_slug}_{source}"
    if key in calibration:
        return float(calibration[key]["sigma"])
    return default_sigma_for_city(city_slug)


def _extract_forecast_value(snapshot: dict, source: str) -> Optional[float]:
    if snapshot.get("source") == source:
        return snapshot.get("temp")
    if snapshot.get("best_source") == source:
        return snapshot.get("best")
    if snapshot.get(source) is not None:
        return snapshot.get(source)
    return snapshot.get("temp")


def run_sigma_calibration(markets: List[dict], calibration_min: int = 30) -> Dict[str, dict]:
    resolved = [
        market for market in markets
        if market.get("status") == "resolved" and market.get("actual_temp") is not None
    ]
    calibration = load_calibration()

    for source in ("ecmwf", "hrrr", "metar"):
        cities = sorted({market["city"] for market in resolved})
        for city in cities:
            residuals = []
            for market in resolved:
                if market["city"] != city:
                    continue
                snapshot = next(
                    (
                        snap
                        for snap in reversed(market.get("forecast_snapshots", []))
                        if snap.get("source") == source or snap.get("best_source") == source or snap.get(source) is not None
                    ),
                    None,
                )
                if snapshot is None:
                    continue
                temp = _extract_forecast_value(snapshot, source)
                actual = market.get("actual_temp")
                if temp is None or actual is None:
                    continue
                residuals.append(float(temp) - float(actual))

            if len(residuals) < calibration_min:
                continue

            sigma = round(pstdev(residuals), 3)
            if sigma <= 0:
                sigma = round(default_sigma_for_city(city), 3)
            calibration[f"{city}_{source}"] = {
                "sigma": sigma,
                "n": len(residuals),
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "method": "residual_stddev",
            }

    save_calibration(calibration)
    return calibration

