"""CLI entrypoint for the package-owned runtime."""

import json
import sys

from weather.backtests.engine import replay_from_storage
from weather.scan import format_paper_scan_report, run_paper_scan
from weather import runtime


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    cmd = args[0] if args else "run"
    if cmd == "run":
        runtime.run_loop()
    elif cmd == "status":
        runtime._cal = runtime.load_cal()
        runtime.print_status()
    elif cmd == "report":
        runtime._cal = runtime.load_cal()
        runtime.print_report()
    elif cmd == "backtest":
        print(json.dumps(replay_from_storage(), indent=2))
    elif cmd == "scan":
        max_price = float(args[1]) if len(args) > 1 else None
        max_slippage = float(args[2]) if len(args) > 2 else None
        print(format_paper_scan_report(run_paper_scan(max_price=max_price, max_slippage=max_slippage)))
    else:
        print("Usage: python -m weather.cli.main [run|status|report|backtest|scan [max_price] [max_slippage]]")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
