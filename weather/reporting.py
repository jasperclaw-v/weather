"""Reporting helpers for status and historical summaries."""


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
