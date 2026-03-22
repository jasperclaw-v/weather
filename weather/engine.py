"""Operational engine for scan, monitor, and resolution passes."""

from datetime import datetime, timezone, timedelta


def scan_and_update(ctx):
    now = datetime.now(timezone.utc)
    state = ctx.load_state()
    balance = state["balance"]
    new_pos = 0
    closed = 0
    resolved = 0

    for city_slug, loc in ctx.LOCATIONS.items():
        unit = loc["unit"]
        unit_sym = "F" if unit == "F" else "C"
        print(f"  -> {loc['name']}...", end=" ", flush=True)

        try:
            dates = [(now + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(4)]
            snapshots = ctx.take_forecast_snapshot(city_slug, dates)
            ctx.sleep(0.3)
        except Exception as exc:
            print(f"skipped ({exc})")
            continue

        for i, date in enumerate(dates):
            dt = datetime.strptime(date, "%Y-%m-%d")
            event = ctx.get_polymarket_event(city_slug, ctx.MONTHS[dt.month - 1], dt.day, dt.year)
            if not event:
                continue

            end_date = event.get("endDate", "")
            hours = ctx.hours_to_resolution(end_date) if end_date else 0
            horizon = f"D+{i}"

            market = ctx.load_market(city_slug, date)
            if market is None:
                if hours < ctx.MIN_HOURS or hours > ctx.MAX_HOURS:
                    continue
                market = ctx.new_market(city_slug, date, event, hours)

            if market["status"] == "resolved":
                continue

            outcomes = ctx.build_outcomes(event)
            market["all_outcomes"] = outcomes

            snap = snapshots.get(date, {})
            forecast_snap = {
                "ts": snap.get("ts"),
                "horizon": horizon,
                "hours_left": round(hours, 1),
                "ecmwf": snap.get("ecmwf"),
                "hrrr": snap.get("hrrr"),
                "metar": snap.get("metar"),
                "best": snap.get("best"),
                "best_source": snap.get("best_source"),
            }
            market["forecast_snapshots"].append(forecast_snap)

            top = max(outcomes, key=lambda item: item["price"]) if outcomes else None
            market["market_snapshots"].append(
                {
                    "ts": snap.get("ts"),
                    "top_bucket": f"{top['range'][0]}-{top['range'][1]}{unit_sym}" if top else None,
                    "top_price": top["price"] if top else None,
                }
            )

            forecast_temp = snap.get("best")
            best_source = snap.get("best_source")

            market, balance, closed_now, exit_reason = ctx.apply_stop_and_forecast_exits(
                market=market,
                outcomes=outcomes,
                forecast_temp=forecast_temp,
                balance=balance,
                ts=snap.get("ts"),
            )
            if closed_now:
                closed += closed_now
                current_price = market["position"]["exit_price"]
                pnl = market["position"]["pnl"]
                if exit_reason == "CLOSE":
                    print(f"  [CLOSE] {loc['name']} {date} — forecast changed | PnL: {'+' if pnl >= 0 else ''}{pnl:.2f}")
                else:
                    print(
                        f"  [{exit_reason}] {loc['name']} {date} | "
                        f"entry ${market['position']['entry_price']:.3f} exit ${current_price:.3f} | "
                        f"PnL: {'+' if pnl >= 0 else ''}{pnl:.2f}"
                    )

            if (not market.get("position") or market["position"].get("status") != "open") and forecast_temp is not None and hours >= ctx.MIN_HOURS:
                sigma = ctx.get_sigma(city_slug, best_source or "ecmwf")
                signal = ctx.select_signal(
                    outcomes=outcomes,
                    forecast_temp=forecast_temp,
                    sigma=sigma,
                    best_source=best_source,
                    opened_at=snap.get("ts"),
                    balance=balance,
                    min_volume=ctx.MIN_VOLUME,
                    min_ev=ctx.MIN_EV,
                    kelly_fraction=ctx.KELLY_FRACTION,
                    max_bet=ctx.MAX_BET,
                )
                if signal:
                    signal, note = ctx.refresh_signal_with_live_quotes(
                        signal,
                        max_slippage=ctx.MAX_SLIPPAGE,
                        max_price=ctx.MAX_PRICE,
                    )
                    if note and note.startswith("skip:"):
                        _, ask, spread = note.split(":")
                        print(f"  [SKIP] {loc['name']} {date} — real ask ${ask} spread ${spread}")
                    elif note and note.startswith("warn:") and signal:
                        print(f"  [WARN] Could not fetch real ask for {signal['market_id']}: {note[5:]}")

                    if signal and signal["entry_price"] < ctx.MAX_PRICE:
                        balance -= signal["cost"]
                        market["position"] = signal
                        state["total_trades"] += 1
                        new_pos += 1
                        bucket_label = f"{signal['bucket_low']}-{signal['bucket_high']}{unit_sym}"
                        print(
                            f"  [BUY]  {loc['name']} {horizon} {date} | {bucket_label} | "
                            f"${signal['entry_price']:.3f} | EV {signal['ev']:+.2f} | "
                            f"${signal['cost']:.2f} ({signal['forecast_src'].upper()})"
                        )

            if hours < 0.5 and market["status"] == "open":
                market["status"] = "closed"

            ctx.save_market(market)
            ctx.sleep(0.1)

        print("ok")

    for market in ctx.load_all_markets():
        if market["status"] == "resolved":
            continue
        position = market.get("position")
        if not position or position.get("status") != "open":
            continue
        market_id = position.get("market_id")
        if not market_id:
            continue
        won = ctx.check_market_resolved(market_id)
        if won is None:
            continue

        market, credit, _outcome = ctx.apply_resolution(market, won, ts=now.isoformat())
        balance += credit
        if won:
            state["wins"] += 1
        else:
            state["losses"] += 1

        pnl = market["pnl"]
        result = "WIN" if won else "LOSS"
        print(f"  [{result}] {market['city_name']} {market['date']} | PnL: {'+' if pnl >= 0 else ''}{pnl:.2f}")
        resolved += 1
        ctx.save_market(market)
        ctx.sleep(0.3)

    state["balance"] = round(balance, 2)
    state["peak_balance"] = max(state.get("peak_balance", balance), balance)
    ctx.save_state(state)

    all_markets = ctx.load_all_markets()
    resolved_count = len([market for market in all_markets if market["status"] == "resolved"])
    if resolved_count >= ctx.CALIBRATION_MIN:
        ctx.set_calibration(ctx.run_calibration(all_markets))

    return new_pos, closed, resolved


def monitor_positions(ctx):
    markets = ctx.load_all_markets()
    open_pos = [market for market in markets if market.get("position") and market["position"].get("status") == "open"]
    if not open_pos:
        return 0

    state = ctx.load_state()
    balance = state["balance"]
    closed = 0

    for market in open_pos:
        position = market["position"]
        market_id = position["market_id"]

        current_price = None
        try:
            response = ctx.requests.get(f"https://gamma-api.polymarket.com/markets/{market_id}", timeout=(3, 5))
            data = response.json()
            best_bid = data.get("bestBid")
            if best_bid is not None:
                current_price = float(best_bid)
        except Exception:
            pass

        if current_price is None:
            for outcome in market.get("all_outcomes", []):
                if outcome["market_id"] == market_id:
                    current_price = outcome.get("bid", outcome["price"])
                    break
        if current_price is None:
            continue

        city_name = ctx.LOCATIONS.get(market["city"], {}).get("name", market["city"])
        end_date = market.get("event_end_date", "")
        hours_left = ctx.hours_to_resolution(end_date) if end_date else 999.0

        pre_stop = position.get("stop_price", position["entry_price"] * 0.80)
        market, did_close, reason = ctx.apply_monitor_exit(
            market=market,
            current_price=current_price,
            hours_left=hours_left,
            schedule=ctx.DEFAULT_TP_SCHEDULE,
        )
        post_stop = position.get("stop_price", pre_stop)
        if post_stop != pre_stop and post_stop == position["entry_price"]:
            print(f"  [TRAILING] {city_name} {market['date']} — stop moved to breakeven ${position['entry_price']:.3f}")
        if did_close:
            pnl = position["pnl"]
            balance += position["cost"] + pnl
            closed += 1
            print(
                f"  [{reason}] {city_name} {market['date']} | entry ${position['entry_price']:.3f} "
                f"exit ${current_price:.3f} | {hours_left:.0f}h left | PnL: {'+' if pnl >= 0 else ''}{pnl:.2f}"
            )
            ctx.save_market(market)

    if closed:
        state["balance"] = round(balance, 2)
        ctx.save_state(state)

    return closed
