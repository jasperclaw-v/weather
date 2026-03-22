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
import json
import time
import requests
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace

from weather.config import load_config
from weather.core.constants import (
    DEFAULT_KELLY_FRACTION,
    DEFAULT_MAX_BET,
    DEFAULT_SIGMA_C,
    DEFAULT_SIGMA_F,
)
from weather.core.finance import bet_size, calc_ev, calc_kelly as core_calc_kelly
from weather.core.probability import bucket_probability as bucket_prob, in_bucket
from weather.data.mapping import LOCATIONS as LOCATION_MODELS, MONTHS
from weather.data.mapping import TIMEZONES
from weather.data.models.metar import get_metar
from weather.data.models.openmeteo import get_ecmwf, get_hrrr
from weather.data.snapshots import take_forecast_snapshot
from weather.data.storage import (
    CALIBRATION_FILE,
    DATA_DIR,
    MARKETS_DIR,
    STATE_FILE,
    load_all_markets,
    load_market,
    load_state as storage_load_state,
    new_market_record,
    save_market,
    save_state as storage_save_state,
)
from weather.execution.polymarket import (
    check_market_resolved,
    get_market_price,
    get_polymarket_event,
    hours_to_resolution,
    parse_temp_range,
)
from weather.strategy.calibration import (
    get_sigma as calibration_get_sigma,
    load_calibration,
    run_sigma_calibration,
)
from weather.strategy.risk import DEFAULT_TP_SCHEDULE, get_tp_threshold
from weather.strategy.lifecycle import (
    apply_monitor_exit,
    apply_resolution,
    apply_stop_and_forecast_exits,
    find_outcome_price,
    refresh_signal_with_live_quotes,
)
from weather.strategy.scanner import build_outcomes, select_signal
from weather.reporting import render_report_header, render_status
from weather.engine import monitor_positions as engine_monitor_positions
from weather.engine import scan_and_update as engine_scan_and_update

# =============================================================================
# CONFIG
# =============================================================================

_cfg = load_config()

BALANCE          = _cfg.get("balance", 10000.0)
MAX_BET          = _cfg.get("max_bet", DEFAULT_MAX_BET)        # max bet per trade
MIN_EV           = _cfg.get("min_ev", 0.10)
MAX_PRICE        = _cfg.get("max_price", 0.45)
MIN_VOLUME       = _cfg.get("min_volume", 500)
MIN_HOURS        = _cfg.get("min_hours", 2.0)
MAX_HOURS        = _cfg.get("max_hours", 72.0)
KELLY_FRACTION   = _cfg.get("kelly_fraction", DEFAULT_KELLY_FRACTION)
MAX_SLIPPAGE     = _cfg.get("max_slippage", 0.03)  # max allowed ask-bid spread
SCAN_INTERVAL    = _cfg.get("scan_interval", 3600)   # every hour
CALIBRATION_MIN  = _cfg.get("calibration_min", 30)
VC_KEY           = _cfg.get("vc_key", "")

SIGMA_F = DEFAULT_SIGMA_F
SIGMA_C = DEFAULT_SIGMA_C

DATA_DIR.mkdir(exist_ok=True)
MARKETS_DIR.mkdir(exist_ok=True)

LOCATIONS = {slug: asdict(location) for slug, location in LOCATION_MODELS.items()}

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
    return SimpleNamespace(
        LOCATIONS=LOCATIONS,
        MONTHS=MONTHS,
        MIN_HOURS=MIN_HOURS,
        MAX_HOURS=MAX_HOURS,
        MIN_VOLUME=MIN_VOLUME,
        MIN_EV=MIN_EV,
        KELLY_FRACTION=KELLY_FRACTION,
        MAX_BET=MAX_BET,
        MAX_SLIPPAGE=MAX_SLIPPAGE,
        MAX_PRICE=MAX_PRICE,
        CALIBRATION_MIN=CALIBRATION_MIN,
        DEFAULT_TP_SCHEDULE=DEFAULT_TP_SCHEDULE,
        requests=requests,
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
    state    = load_state()
    markets  = load_all_markets()
    open_pos = [m for m in markets if m.get("position") and m["position"].get("status") == "open"]
    resolved = [m for m in markets if m["status"] == "resolved" and m.get("pnl") is not None]

    bal     = state["balance"]
    start   = state["starting_balance"]
    ret_pct = (bal - start) / start * 100
    wins    = state["wins"]
    losses  = state["losses"]
    total   = wins + losses

    print(render_status(state, open_pos))
    print(f"  Resolved:    {len(resolved)}")

    if open_pos:
        print(f"\n  Open positions:")
        total_unrealized = 0.0
        for m in open_pos:
            pos      = m["position"]
            unit_sym = "F" if m["unit"] == "F" else "C"
            label    = f"{pos['bucket_low']}-{pos['bucket_high']}{unit_sym}"

            # Current price from latest market snapshot
            current_price = pos["entry_price"]
            snaps = m.get("market_snapshots", [])
            if snaps:
                # Find our bucket price in all_outcomes
                current_price = find_outcome_price(m.get("all_outcomes", []), pos["market_id"], side="price") or current_price

            unrealized = round((current_price - pos["entry_price"]) * pos["shares"], 2)
            total_unrealized += unrealized
            pnl_str = f"{'+'if unrealized>=0 else ''}{unrealized:.2f}"

            print(f"    {m['city_name']:<16} {m['date']} | {label:<14} | "
                  f"entry ${pos['entry_price']:.3f} -> ${current_price:.3f} | "
                  f"PnL: {pnl_str} | {pos['forecast_src'].upper()}")

        sign = "+" if total_unrealized >= 0 else ""
        print(f"\n  Unrealized PnL: {sign}{total_unrealized:.2f}")

    print(f"{'='*55}\n")

def print_report():
    markets  = load_all_markets()
    resolved = [m for m in markets if m["status"] == "resolved" and m.get("pnl") is not None]

    print(render_report_header(resolved))

    if not resolved:
        return

    total_pnl = sum(m["pnl"] for m in resolved)
    wins      = [m for m in resolved if m["resolved_outcome"] == "win"]
    losses    = [m for m in resolved if m["resolved_outcome"] == "loss"]

    print(f"\n  Total resolved: {len(resolved)}")
    print(f"  Wins:           {len(wins)} | Losses: {len(losses)}")
    print(f"  Win rate:       {len(wins)/len(resolved):.0%}")
    print(f"  Total PnL:      {'+'if total_pnl>=0 else ''}{total_pnl:.2f}")

    print(f"\n  By city:")
    for city in sorted(set(m["city"] for m in resolved)):
        group = [m for m in resolved if m["city"] == city]
        w     = len([m for m in group if m["resolved_outcome"] == "win"])
        pnl   = sum(m["pnl"] for m in group)
        name  = LOCATIONS[city]["name"]
        print(f"    {name:<16} {w}/{len(group)} ({w/len(group):.0%})  PnL: {'+'if pnl>=0 else ''}{pnl:.2f}")

    print(f"\n  Market details:")
    for m in sorted(resolved, key=lambda x: x["date"]):
        pos      = m.get("position", {})
        unit_sym = "F" if m["unit"] == "F" else "C"
        snaps    = m.get("forecast_snapshots", [])
        first_fc = snaps[0]["best"] if snaps else None
        last_fc  = snaps[-1]["best"] if snaps else None
        label    = f"{pos.get('bucket_low')}-{pos.get('bucket_high')}{unit_sym}" if pos else "no position"
        result   = m["resolved_outcome"].upper()
        pnl_str  = f"{'+'if m['pnl']>=0 else ''}{m['pnl']:.2f}" if m["pnl"] is not None else "-"
        fc_str   = f"forecast {first_fc}->{last_fc}{unit_sym}" if first_fc else "no forecast"
        actual   = f"actual {m['actual_temp']}{unit_sym}" if m["actual_temp"] else ""
        print(f"    {m['city_name']:<16} {m['date']} | {label:<14} | {fc_str} | {actual} | {result} {pnl_str}")

    print(f"{'='*55}\n")

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
