"""Application configuration and runtime context assembly."""

from dataclasses import asdict, dataclass
from types import SimpleNamespace
from typing import Any, Callable, Dict

import requests

from weather.config import load_config
from weather.core.constants import (
    DEFAULT_KELLY_FRACTION,
    DEFAULT_MAX_BET,
    DEFAULT_SIGMA_C,
    DEFAULT_SIGMA_F,
)
from weather.data.mapping import LOCATIONS as LOCATION_MODELS, MONTHS
from weather.execution.auth import load_polymarket_auth_from_env
from weather.execution.service import ExecutionService
from weather.strategy.risk import DEFAULT_TP_SCHEDULE


@dataclass
class RuntimeConfig:
    balance: float = 10000.0
    max_bet: float = DEFAULT_MAX_BET
    min_ev: float = 0.10
    max_price: float = 0.45
    min_volume: float = 500
    min_hours: float = 2.0
    max_hours: float = 72.0
    kelly_fraction: float = DEFAULT_KELLY_FRACTION
    max_slippage: float = 0.03
    scan_interval: int = 3600
    calibration_min: int = 30
    sigma_f: float = DEFAULT_SIGMA_F
    sigma_c: float = DEFAULT_SIGMA_C


def load_runtime_config() -> RuntimeConfig:
    raw = load_config()
    return RuntimeConfig(
        balance=raw.get("balance", 10000.0),
        max_bet=raw.get("max_bet", DEFAULT_MAX_BET),
        min_ev=raw.get("min_ev", 0.10),
        max_price=raw.get("max_price", 0.45),
        min_volume=raw.get("min_volume", 500),
        min_hours=raw.get("min_hours", 2.0),
        max_hours=raw.get("max_hours", 72.0),
        kelly_fraction=raw.get("kelly_fraction", DEFAULT_KELLY_FRACTION),
        max_slippage=raw.get("max_slippage", 0.03),
        scan_interval=raw.get("scan_interval", 3600),
        calibration_min=raw.get("calibration_min", 30),
    )


def runtime_locations() -> Dict[str, Dict[str, Any]]:
    return {slug: asdict(location) for slug, location in LOCATION_MODELS.items()}


def build_runtime_context(
    *,
    locations: Dict[str, Dict[str, Any]],
    config: RuntimeConfig,
    sleep: Callable[[float], None],
    load_state: Callable[[], dict],
    save_state: Callable[[dict], None],
    load_market: Callable[[str, str], dict],
    save_market: Callable[[dict], None],
    load_all_markets: Callable[[], list],
    new_market: Callable[[str, str, dict, float], dict],
    take_forecast_snapshot: Callable[..., dict],
    get_polymarket_event: Callable[..., dict],
    hours_to_resolution: Callable[[str], float],
    build_outcomes: Callable[[dict], list],
    apply_stop_and_forecast_exits: Callable[..., tuple],
    get_sigma: Callable[[str, str], float],
    select_signal: Callable[..., dict],
    refresh_signal_with_live_quotes: Callable[..., tuple],
    check_market_resolved: Callable[[str], bool],
    apply_resolution: Callable[..., tuple],
    run_calibration: Callable[[list], dict],
    set_calibration: Callable[[dict], None],
    apply_monitor_exit: Callable[..., tuple],
    execution_service: Any = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        LOCATIONS=locations,
        MONTHS=MONTHS,
        MIN_HOURS=config.min_hours,
        MAX_HOURS=config.max_hours,
        MIN_VOLUME=config.min_volume,
        MIN_EV=config.min_ev,
        KELLY_FRACTION=config.kelly_fraction,
        MAX_BET=config.max_bet,
        MAX_SLIPPAGE=config.max_slippage,
        MAX_PRICE=config.max_price,
        CALIBRATION_MIN=config.calibration_min,
        DEFAULT_TP_SCHEDULE=DEFAULT_TP_SCHEDULE,
        requests=requests,
        sleep=sleep,
        load_state=load_state,
        save_state=save_state,
        load_market=load_market,
        save_market=save_market,
        load_all_markets=load_all_markets,
        new_market=new_market,
        take_forecast_snapshot=take_forecast_snapshot,
        get_polymarket_event=get_polymarket_event,
        hours_to_resolution=hours_to_resolution,
        build_outcomes=build_outcomes,
        apply_stop_and_forecast_exits=apply_stop_and_forecast_exits,
        get_sigma=get_sigma,
        select_signal=select_signal,
        refresh_signal_with_live_quotes=refresh_signal_with_live_quotes,
        check_market_resolved=check_market_resolved,
        apply_resolution=apply_resolution,
        run_calibration=run_calibration,
        set_calibration=set_calibration,
        apply_monitor_exit=apply_monitor_exit,
        execution_service=execution_service,
    )


def build_execution_service() -> ExecutionService:
    return ExecutionService.from_auth_config(load_polymarket_auth_from_env())
