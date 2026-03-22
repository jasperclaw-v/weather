#!/usr/bin/env python3
"""Compatibility wrapper for the package-owned runtime."""

import sys

from weather.runtime import *  # noqa: F401,F403


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
    elif cmd == "backtest":
        from weather.backtests.engine import replay_from_storage
        import json

        print(json.dumps(replay_from_storage(), indent=2))
    elif cmd == "scan":
        from weather.scan import format_paper_scan_report, run_paper_scan

        max_price = float(sys.argv[2]) if len(sys.argv) > 2 else None
        max_slippage = float(sys.argv[3]) if len(sys.argv) > 3 else None
        print(format_paper_scan_report(run_paper_scan(max_price=max_price, max_slippage=max_slippage)))
    elif cmd == "dashboard":
        from weather.ui.dashboard import launch_dashboard

        raise SystemExit(launch_dashboard())
    else:
        print("Usage: python weatherbet.py [run|status|report|backtest|scan [max_price] [max_slippage]|dashboard]")
