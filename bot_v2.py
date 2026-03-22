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
    else:
        print("Usage: python weatherbet.py [run|status|report|backtest]")
