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
from weather.strategy.scanner import build_outcomes, select_signal

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

def scan_and_update():
    """Main function of one cycle: updates forecasts, opens/closes positions."""
    global _cal
    now      = datetime.now(timezone.utc)
    state    = load_state()
    balance  = state["balance"]
    new_pos  = 0
    closed   = 0
    resolved = 0

    for city_slug, loc in LOCATIONS.items():
        unit = loc["unit"]
        unit_sym = "F" if unit == "F" else "C"
        print(f"  -> {loc['name']}...", end=" ", flush=True)

        try:
            dates = [(now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(4)]
            snapshots = take_forecast_snapshot(city_slug, dates)
            time.sleep(0.3)
        except Exception as e:
            print(f"skipped ({e})")
            continue

        for i, date in enumerate(dates):
            dt    = datetime.strptime(date, "%Y-%m-%d")
            event = get_polymarket_event(city_slug, MONTHS[dt.month - 1], dt.day, dt.year)
            if not event:
                continue

            end_date = event.get("endDate", "")
            hours    = hours_to_resolution(end_date) if end_date else 0
            horizon  = f"D+{i}"

            # Load or create market record
            mkt = load_market(city_slug, date)
            if mkt is None:
                if hours < MIN_HOURS or hours > MAX_HOURS:
                    continue
                mkt = new_market(city_slug, date, event, hours)

            # Skip if market already resolved
            if mkt["status"] == "resolved":
                continue

            # Update outcomes list — prices taken directly from event
            outcomes = build_outcomes(event)
            mkt["all_outcomes"] = outcomes

            # Forecast snapshot
            snap = snapshots.get(date, {})
            forecast_snap = {
                "ts":          snap.get("ts"),
                "horizon":     horizon,
                "hours_left":  round(hours, 1),
                "ecmwf":       snap.get("ecmwf"),
                "hrrr":        snap.get("hrrr"),
                "metar":       snap.get("metar"),
                "best":        snap.get("best"),
                "best_source": snap.get("best_source"),
            }
            mkt["forecast_snapshots"].append(forecast_snap)

            # Market price snapshot
            top = max(outcomes, key=lambda x: x["price"]) if outcomes else None
            market_snap = {
                "ts":       snap.get("ts"),
                "top_bucket": f"{top['range'][0]}-{top['range'][1]}{unit_sym}" if top else None,
                "top_price":  top["price"] if top else None,
            }
            mkt["market_snapshots"].append(market_snap)

            forecast_temp = snap.get("best")
            best_source   = snap.get("best_source")

            # --- STOP-LOSS AND TRAILING STOP ---
            if mkt.get("position") and mkt["position"].get("status") == "open":
                pos = mkt["position"]
                current_price = None
                for o in outcomes:
                    if o["market_id"] == pos["market_id"]:
                        current_price = o["price"]
                        break

                if current_price is not None:
                    current_price = o.get("bid", current_price)  # sell at bid
                    entry = pos["entry_price"]
                    stop  = pos.get("stop_price", entry * 0.80)  # 20% stop by default

                    # Trailing: if up 20%+ — move stop to breakeven
                    if current_price >= entry * 1.20 and stop < entry:
                        pos["stop_price"] = entry
                        pos["trailing_activated"] = True

                    # Check stop
                    if current_price <= stop:
                        pnl = round((current_price - entry) * pos["shares"], 2)
                        balance += pos["cost"] + pnl
                        pos["closed_at"]    = snap.get("ts")
                        pos["close_reason"] = "stop_loss" if current_price < entry else "trailing_stop"
                        pos["exit_price"]   = current_price
                        pos["pnl"]          = pnl
                        pos["status"]       = "closed"
                        closed += 1
                        reason = "STOP" if current_price < entry else "TRAILING BE"
                        print(f"  [{reason}] {loc['name']} {date} | entry ${entry:.3f} exit ${current_price:.3f} | PnL: {'+'if pnl>=0 else ''}{pnl:.2f}")

            # --- CLOSE POSITION if forecast shifted 2+ degrees ---
            if mkt.get("position") and forecast_temp is not None:
                pos = mkt["position"]
                old_bucket_low  = pos["bucket_low"]
                old_bucket_high = pos["bucket_high"]
                # 2-degree buffer — avoid closing on small forecast fluctuations
                unit = loc["unit"]
                buffer = 2.0 if unit == "F" else 1.0
                mid_bucket = (old_bucket_low + old_bucket_high) / 2 if old_bucket_low != -999 and old_bucket_high != 999 else forecast_temp
                forecast_far = abs(forecast_temp - mid_bucket) > (abs(mid_bucket - old_bucket_low) + buffer)
                if not in_bucket(forecast_temp, old_bucket_low, old_bucket_high) and forecast_far:
                    current_price = None
                    for o in outcomes:
                        if o["market_id"] == pos["market_id"]:
                            current_price = o["price"]
                            break
                    if current_price is not None:
                        pnl = round((current_price - pos["entry_price"]) * pos["shares"], 2)
                        balance += pos["cost"] + pnl
                        mkt["position"]["closed_at"]    = snap.get("ts")
                        mkt["position"]["close_reason"] = "forecast_changed"
                        mkt["position"]["exit_price"]   = current_price
                        mkt["position"]["pnl"]          = pnl
                        mkt["position"]["status"]       = "closed"
                        closed += 1
                        print(f"  [CLOSE] {loc['name']} {date} — forecast changed | PnL: {'+'if pnl>=0 else ''}{pnl:.2f}")

            # --- OPEN POSITION ---
            if not mkt.get("position") and forecast_temp is not None and hours >= MIN_HOURS:
                sigma = get_sigma(city_slug, best_source or "ecmwf")
                best_signal = select_signal(
                    outcomes=outcomes,
                    forecast_temp=forecast_temp,
                    sigma=sigma,
                    best_source=best_source,
                    opened_at=snap.get("ts"),
                    balance=balance,
                    min_volume=MIN_VOLUME,
                    min_ev=MIN_EV,
                    kelly_fraction=KELLY_FRACTION,
                    max_bet=MAX_BET,
                )

                if best_signal:
                    # Fetch real bestAsk from Polymarket API for accurate entry price
                    skip_position = False
                    try:
                        r = requests.get(f"https://gamma-api.polymarket.com/markets/{best_signal['market_id']}", timeout=(3, 5))
                        mdata = r.json()
                        real_ask = float(mdata.get("bestAsk", best_signal["entry_price"]))
                        real_bid = float(mdata.get("bestBid", best_signal["bid_at_entry"]))
                        real_spread = round(real_ask - real_bid, 4)
                        # Re-check slippage and price with real values
                        if real_spread > MAX_SLIPPAGE or real_ask >= MAX_PRICE:
                            print(f"  [SKIP] {loc['name']} {date} — real ask ${real_ask:.3f} spread ${real_spread:.3f}")
                            skip_position = True
                        else:
                            best_signal["entry_price"]  = real_ask
                            best_signal["bid_at_entry"] = real_bid
                            best_signal["spread"]       = real_spread
                            best_signal["shares"]       = round(best_signal["cost"] / real_ask, 2)
                            best_signal["ev"]           = round(calc_ev(best_signal["p"], real_ask), 4)
                    except Exception as e:
                        print(f"  [WARN] Could not fetch real ask for {best_signal['market_id']}: {e}")

                    if not skip_position and best_signal["entry_price"] < MAX_PRICE:
                        balance -= best_signal["cost"]
                        mkt["position"] = best_signal
                        state["total_trades"] += 1
                        new_pos += 1
                        bucket_label = f"{best_signal['bucket_low']}-{best_signal['bucket_high']}{unit_sym}"
                        print(f"  [BUY]  {loc['name']} {horizon} {date} | {bucket_label} | "
                              f"${best_signal['entry_price']:.3f} | EV {best_signal['ev']:+.2f} | "
                              f"${best_signal['cost']:.2f} ({best_signal['forecast_src'].upper()})")

            # Market closed by time
            if hours < 0.5 and mkt["status"] == "open":
                mkt["status"] = "closed"

            save_market(mkt)
            time.sleep(0.1)

        print("ok")

    # --- AUTO-RESOLUTION ---
    for mkt in load_all_markets():
        if mkt["status"] == "resolved":
            continue

        pos = mkt.get("position")
        if not pos or pos.get("status") != "open":
            continue

        market_id = pos.get("market_id")
        if not market_id:
            continue

        # Check if market closed on Polymarket
        won = check_market_resolved(market_id)
        if won is None:
            continue  # market still open

        # Market closed — record result
        price  = pos["entry_price"]
        size   = pos["cost"]
        shares = pos["shares"]
        pnl    = round(shares * (1 - price), 2) if won else round(-size, 2)

        balance += size + pnl
        pos["exit_price"]   = 1.0 if won else 0.0
        pos["pnl"]          = pnl
        pos["close_reason"] = "resolved"
        pos["closed_at"]    = now.isoformat()
        pos["status"]       = "closed"
        mkt["pnl"]          = pnl
        mkt["status"]       = "resolved"
        mkt["resolved_outcome"] = "win" if won else "loss"

        if won:
            state["wins"] += 1
        else:
            state["losses"] += 1

        result = "WIN" if won else "LOSS"
        print(f"  [{result}] {mkt['city_name']} {mkt['date']} | PnL: {'+'if pnl>=0 else ''}{pnl:.2f}")
        resolved += 1

        save_market(mkt)
        time.sleep(0.3)

    state["balance"]      = round(balance, 2)
    state["peak_balance"] = max(state.get("peak_balance", balance), balance)
    save_state(state)

    # Run calibration if enough data collected
    all_mkts = load_all_markets()
    resolved_count = len([m for m in all_mkts if m["status"] == "resolved"])
    if resolved_count >= CALIBRATION_MIN:
        global _cal
        _cal = run_calibration(all_mkts)

    return new_pos, closed, resolved

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

    print(f"\n{'='*55}")
    print(f"  WEATHERBET — STATUS")
    print(f"{'='*55}")
    print(f"  Balance:     ${bal:,.2f}  (start ${start:,.2f}, {'+'if ret_pct>=0 else ''}{ret_pct:.1f}%)")
    print(f"  Trades:      {total} | W: {wins} | L: {losses} | WR: {wins/total:.0%}" if total else "  No trades yet")
    print(f"  Open:        {len(open_pos)}")
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
                for o in m.get("all_outcomes", []):
                    if o["market_id"] == pos["market_id"]:
                        current_price = o["price"]
                        break

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

    print(f"\n{'='*55}")
    print(f"  WEATHERBET — FULL REPORT")
    print(f"{'='*55}")

    if not resolved:
        print("  No resolved markets yet.")
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
    """Quick stop check on open positions without full scan."""
    markets  = load_all_markets()
    open_pos = [m for m in markets if m.get("position") and m["position"].get("status") == "open"]
    if not open_pos:
        return 0

    state   = load_state()
    balance = state["balance"]
    closed  = 0

    for mkt in open_pos:
        pos = mkt["position"]
        mid = pos["market_id"]

        # Fetch real bestBid from Polymarket API — actual sell price
        current_price = None
        try:
            r = requests.get(f"https://gamma-api.polymarket.com/markets/{mid}", timeout=(3, 5))
            mdata = r.json()
            best_bid = mdata.get("bestBid")
            if best_bid is not None:
                current_price = float(best_bid)
        except Exception:
            pass

        # Fallback to cached price if API failed
        if current_price is None:
            for o in mkt.get("all_outcomes", []):
                if o["market_id"] == mid:
                    current_price = o.get("bid", o["price"])
                    break

        if current_price is None:
            continue

        entry = pos["entry_price"]
        stop  = pos.get("stop_price", entry * 0.80)
        city_name = LOCATIONS.get(mkt["city"], {}).get("name", mkt["city"])

        # Hours left to resolution
        end_date = mkt.get("event_end_date", "")
        hours_left = hours_to_resolution(end_date) if end_date else 999.0

        take_profit = get_tp_threshold(hours_left, DEFAULT_TP_SCHEDULE)

        # Trailing: if up 20%+ — move stop to breakeven
        if current_price >= entry * 1.20 and stop < entry:
            pos["stop_price"] = entry
            pos["trailing_activated"] = True
            print(f"  [TRAILING] {city_name} {mkt['date']} — stop moved to breakeven ${entry:.3f}")

        # Check take-profit
        take_triggered = take_profit is not None and current_price >= take_profit
        # Check stop
        stop_triggered = current_price <= stop

        if take_triggered or stop_triggered:
            pnl = round((current_price - entry) * pos["shares"], 2)
            balance += pos["cost"] + pnl
            pos["closed_at"]    = datetime.now(timezone.utc).isoformat()
            if take_triggered:
                pos["close_reason"] = "take_profit"
                reason = "TAKE"
            elif current_price < entry:
                pos["close_reason"] = "stop_loss"
                reason = "STOP"
            else:
                pos["close_reason"] = "trailing_stop"
                reason = "TRAILING BE"
            pos["exit_price"]   = current_price
            pos["pnl"]          = pnl
            pos["status"]       = "closed"
            closed += 1
            print(f"  [{reason}] {city_name} {mkt['date']} | entry ${entry:.3f} exit ${current_price:.3f} | {hours_left:.0f}h left | PnL: {'+'if pnl>=0 else ''}{pnl:.2f}")
            save_market(mkt)

    if closed:
        state["balance"] = round(balance, 2)
        save_state(state)

    return closed


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
