"""Reporting helpers for status and historical summaries."""


def print_status_report(*, state: dict, markets: list[dict], find_outcome_price) -> None:
    open_positions = [market for market in markets if market.get("position") and market["position"].get("status") == "open"]
    resolved = [market for market in markets if market["status"] == "resolved" and market.get("pnl") is not None]

    print(render_status(state, open_positions))
    print(f"  Resolved:    {len(resolved)}")

    if open_positions:
        print("\n  Open positions:")
        total_unrealized = 0.0
        for market in open_positions:
            position = market["position"]
            unit_sym = "F" if market["unit"] == "F" else "C"
            label = f"{position['bucket_low']}-{position['bucket_high']}{unit_sym}"
            current_price = position["entry_price"]
            if market.get("market_snapshots"):
                current_price = find_outcome_price(market.get("all_outcomes", []), position["market_id"], side="price") or current_price
            unrealized = round((current_price - position["entry_price"]) * position["shares"], 2)
            total_unrealized += unrealized
            pnl_str = f"{'+' if unrealized >= 0 else ''}{unrealized:.2f}"
            print(
                f"    {market['city_name']:<16} {market['date']} | {label:<14} | "
                f"entry ${position['entry_price']:.3f} -> ${current_price:.3f} | "
                f"PnL: {pnl_str} | {position['forecast_src'].upper()}"
            )
        sign = "+" if total_unrealized >= 0 else ""
        print(f"\n  Unrealized PnL: {sign}{total_unrealized:.2f}")

    print(f"{'='*55}\n")


def print_full_report(*, resolved: list[dict], locations: dict) -> None:
    print(render_report_header(resolved))
    if not resolved:
        return

    total_pnl = sum(market["pnl"] for market in resolved)
    wins = [market for market in resolved if market["resolved_outcome"] == "win"]
    losses = [market for market in resolved if market["resolved_outcome"] == "loss"]

    print(f"\n  Total resolved: {len(resolved)}")
    print(f"  Wins:           {len(wins)} | Losses: {len(losses)}")
    print(f"  Win rate:       {len(wins)/len(resolved):.0%}")
    print(f"  Total PnL:      {'+' if total_pnl >= 0 else ''}{total_pnl:.2f}")

    print("\n  By city:")
    for city in sorted(set(market["city"] for market in resolved)):
        group = [market for market in resolved if market["city"] == city]
        wins_for_city = len([market for market in group if market["resolved_outcome"] == "win"])
        pnl = sum(market["pnl"] for market in group)
        name = locations[city]["name"]
        print(f"    {name:<16} {wins_for_city}/{len(group)} ({wins_for_city/len(group):.0%})  PnL: {'+' if pnl >= 0 else ''}{pnl:.2f}")

    print("\n  Market details:")
    for market in sorted(resolved, key=lambda item: item["date"]):
        position = market.get("position", {})
        unit_sym = "F" if market["unit"] == "F" else "C"
        snapshots = market.get("forecast_snapshots", [])
        first_fc = snapshots[0]["best"] if snapshots else None
        last_fc = snapshots[-1]["best"] if snapshots else None
        label = f"{position.get('bucket_low')}-{position.get('bucket_high')}{unit_sym}" if position else "no position"
        result = market["resolved_outcome"].upper()
        pnl_str = f"{'+' if market['pnl'] >= 0 else ''}{market['pnl']:.2f}" if market["pnl"] is not None else "-"
        fc_str = f"forecast {first_fc}->{last_fc}{unit_sym}" if first_fc else "no forecast"
        actual = f"actual {market['actual_temp']}{unit_sym}" if market["actual_temp"] else ""
        print(f"    {market['city_name']:<16} {market['date']} | {label:<14} | {fc_str} | {actual} | {result} {pnl_str}")

    print(f"{'='*55}\n")


def render_status(state: dict, open_positions: list[dict]) -> str:
    bal = state["balance"]
    start = state["starting_balance"]
    ret_pct = (bal - start) / start * 100
    wins = state["wins"]
    losses = state["losses"]
    total = wins + losses

    lines = [
        "",
        "=" * 55,
        "  WEATHERBET — STATUS",
        "=" * 55,
        f"  Balance:     ${bal:,.2f}  (start ${start:,.2f}, {'+' if ret_pct >= 0 else ''}{ret_pct:.1f}%)",
        f"  Trades:      {total} | W: {wins} | L: {losses} | WR: {wins/total:.0%}" if total else "  No trades yet",
        f"  Open:        {len(open_positions)}",
    ]
    return "\n".join(lines)


def render_report_header(resolved_markets: list[dict]) -> str:
    lines = [
        "",
        "=" * 55,
        "  WEATHERBET — FULL REPORT",
        "=" * 55,
    ]
    if not resolved_markets:
        lines.append("  No resolved markets yet.")
    return "\n".join(lines)
