#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
weatherbet.py — Weather Trading Bot for Polymarket
=====================================================
Tracks weather forecasts from 3 sources (ECMWF, HRRR, METAR),
compares with Polymarket markets, paper trades using Kelly criterion.

Usage:
    python weatherbet.py          # main loop
    python weatherbet.py report   # full report
    python weatherbet.py status   # balance and open positions
"""

import sys
import time
import requests
from datetime import datetime

from weather.app import build_runtime_context, load_runtime_config, runtime_locations
from weather.core.finance import calc_kelly as core_calc_kelly
from weather.data.snapshots import take_forecast_snapshot
from weather.data.storage import (
    DATA_DIR,
    MARKETS_DIR,
    load_all_markets,
    load_market,
    load_state as storage_load_state,
    new_market_record,
    save_market,
    save_state as storage_save_state,
)
from weather.execution.polymarket import (
    check_market_resolved,
    get_polymarket_event,
    hours_to_resolution,
)
from weather.strategy.calibration import (
    get_sigma as calibration_get_sigma,
    load_calibration,
    run_sigma_calibration,
)
from weather.strategy.risk import DEFAULT_TP_SCHEDULE
from weather.strategy.lifecycle import (
    apply_monitor_exit,
    apply_resolution,
    apply_stop_and_forecast_exits,
    find_outcome_price,
    refresh_signal_with_live_quotes,
)
from weather.strategy.scanner import build_outcomes, select_signal
from weather.reporting import print_full_report, print_status_report
from weather.engine import monitor_positions as engine_monitor_positions
from weather.engine import scan_and_update as engine_scan_and_update

CONFIG = load_runtime_config()

BALANCE = CONFIG.balance
MAX_BET = CONFIG.max_bet
MIN_EV = CONFIG.min_ev
MAX_PRICE = CONFIG.max_price
MIN_VOLUME = CONFIG.min_volume
MIN_HOURS = CONFIG.min_hours
MAX_HOURS = CONFIG.max_hours
KELLY_FRACTION = CONFIG.kelly_fraction
MAX_SLIPPAGE = CONFIG.max_slippage
SCAN_INTERVAL = CONFIG.scan_interval
CALIBRATION_MIN = CONFIG.calibration_min
SIGMA_F = CONFIG.sigma_f
SIGMA_C = CONFIG.sigma_c

DATA_DIR.mkdir(exist_ok=True)
MARKETS_DIR.mkdir(exist_ok=True)

LOCATIONS = runtime_locations()

_cal: dict = {}


def calc_kelly(p, price):
    return core_calc_kelly(p, price, fraction=KELLY_FRACTION)

def load_cal():
    return load_calibration()

def get_sigma(city_slug, source="ecmwf"):
    return calibration_get_sigma(city_slug, source=source, calibration=_cal)

def run_calibration(markets):
    return run_sigma_calibration(markets, calibration_min=CALIBRATION_MIN)

# =============================================================================
# MARKET DATA STORAGE
# Each market is stored in a separate file: data/markets/{city}_{date}.json
# =============================================================================

def new_market(city_slug, date_str, event, hours):
    loc = LOCATIONS[city_slug]
    return new_market_record(city_slug, loc, date_str, event, hours)

# =============================================================================
# STATE (balance and open positions)
# =============================================================================

def load_state():
    return storage_load_state(default_balance=BALANCE)

def save_state(state):
    storage_save_state(state)

def _set_calibration(value):
    global _cal
    _cal = value


def runtime_context():
    return build_runtime_context(
        locations=LOCATIONS,
        config=CONFIG,
        sleep=time.sleep,
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
        set_calibration=_set_calibration,
        apply_monitor_exit=apply_monitor_exit,
    )


def scan_and_update():
    return engine_scan_and_update(runtime_context())

# =============================================================================
# REPORT
# =============================================================================

def print_status():
    print_status_report(
        state=load_state(),
        markets=load_all_markets(),
        find_outcome_price=find_outcome_price,
    )

def print_report():
    markets = load_all_markets()
    resolved = [m for m in markets if m["status"] == "resolved" and m.get("pnl") is not None]
    print_full_report(resolved=resolved, locations=LOCATIONS)

# =============================================================================
# MAIN LOOP
# =============================================================================

MONITOR_INTERVAL = 600  # monitor positions every 10 minutes

def monitor_positions():
    return engine_monitor_positions(runtime_context())


def run_loop():
    global _cal
    _cal = load_cal()

    print(f"\n{'='*55}")
    print(f"  WEATHERBET — STARTING")
    print(f"{'='*55}")
    print(f"  Cities:     {len(LOCATIONS)}")
    print(f"  Balance:    ${BALANCE:,.0f} | Max bet: ${MAX_BET}")
    print(f"  Scan:       {SCAN_INTERVAL//60} min | Monitor: {MONITOR_INTERVAL//60} min")
    print(f"  Sources:    ECMWF + HRRR(US) + METAR(D+0)")
    print(f"  Data:       {DATA_DIR.resolve()}")
    print(f"  Ctrl+C to stop\n")

    last_full_scan = 0

    while True:
        now_ts  = time.time()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Full scan once per hour
        if now_ts - last_full_scan >= SCAN_INTERVAL:
            print(f"[{now_str}] full scan...")
            try:
                new_pos, closed, resolved = scan_and_update()
                state = load_state()
                print(f"  balance: ${state['balance']:,.2f} | "
                      f"new: {new_pos} | closed: {closed} | resolved: {resolved}")
                last_full_scan = time.time()
            except KeyboardInterrupt:
                print(f"\n  Stopping — saving state...")
                save_state(load_state())
                print(f"  Done. Bye!")
                break
            except requests.exceptions.ConnectionError:
                print(f"  Connection lost — waiting 60 sec")
                time.sleep(60)
                continue
            except Exception as e:
                print(f"  Error: {e} — waiting 60 sec")
                time.sleep(60)
                continue
        else:
            # Quick stop monitoring
            print(f"[{now_str}] monitoring positions...")
            try:
                stopped = monitor_positions()
                if stopped:
                    state = load_state()
                    print(f"  balance: ${state['balance']:,.2f}")
            except Exception as e:
                print(f"  Monitor error: {e}")

        try:
            time.sleep(MONITOR_INTERVAL)
        except KeyboardInterrupt:
            print(f"\n  Stopping — saving state...")
            save_state(load_state())
            print(f"  Done. Bye!")
            break

# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"
    if cmd == "run":
        run_loop()
    elif cmd == "status":
        _cal = load_cal()
        print_status()
    elif cmd == "report":
        _cal = load_cal()
        print_report()
    else:
        print("Usage: python weatherbet.py [run|status|report]")
