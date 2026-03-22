"""Position-level risk controls."""

from typing import List, Optional

from weather.core.types import RiskResult

DEFAULT_TP_SCHEDULE = [
    {"hours_min": 48, "hours_max": 9999, "threshold": 0.75},
    {"hours_min": 24, "hours_max": 48, "threshold": 0.85},
    {"hours_min": 0, "hours_max": 24, "threshold": None},
]

STOP_LOSS_PCT = 0.20
TRAILING_ACTIVATION = 1.20
FORECAST_DRIFT_F = 2.0
FORECAST_DRIFT_C = 1.0


def get_tp_threshold(hours_left: float, schedule: Optional[List[dict]] = None) -> Optional[float]:
    active = schedule or DEFAULT_TP_SCHEDULE
    for band in active:
        if band["hours_min"] <= hours_left < band["hours_max"]:
            return band["threshold"]
    return None


def evaluate_position(
    entry_price: float,
    current_price: float,
    shares: float,
    hours_left: float,
    stop_price: Optional[float] = None,
    trailing_activated: bool = False,
    forecast_temp: Optional[float] = None,
    bucket_low: float = 0.0,
    bucket_high: float = 0.0,
    unit: str = "F",
    tp_schedule: Optional[List[dict]] = None,
) -> RiskResult:
    result = RiskResult(trailing_activated=trailing_activated)
    stop = stop_price if stop_price is not None else entry_price * (1.0 - STOP_LOSS_PCT)

    if current_price >= entry_price * TRAILING_ACTIVATION and stop < entry_price:
        stop = entry_price
        result.trailing_activated = True

    if current_price <= stop:
        pnl = round((current_price - entry_price) * shares, 2)
        reason = "stop_loss" if current_price < entry_price else "trailing_stop"
        return RiskResult("close", reason, current_price, pnl, result.trailing_activated)

    take_profit = get_tp_threshold(hours_left, tp_schedule)
    if take_profit is not None and current_price >= take_profit:
        pnl = round((current_price - entry_price) * shares, 2)
        return RiskResult("close", "take_profit", current_price, pnl, result.trailing_activated)

    if forecast_temp is not None and bucket_low > -999 and bucket_high < 999:
        buffer_value = FORECAST_DRIFT_F if unit == "F" else FORECAST_DRIFT_C
        mid_bucket = (bucket_low + bucket_high) / 2.0
        half_width = (bucket_high - bucket_low) / 2.0
        if abs(forecast_temp - mid_bucket) > half_width + buffer_value:
            pnl = round((current_price - entry_price) * shares, 2)
            return RiskResult("close", "forecast_changed", current_price, pnl, result.trailing_activated)

    return result

