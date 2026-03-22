"""Compatibility CLI that delegates to the current legacy runner."""

import sys

import bot_v2


def main(argv=None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    cmd = args[0] if args else "run"
    if cmd == "run":
        bot_v2.run_loop()
    elif cmd == "status":
        bot_v2._cal = bot_v2.load_cal()
        bot_v2.print_status()
    elif cmd == "report":
        bot_v2._cal = bot_v2.load_cal()
        bot_v2.print_report()
    else:
        print("Usage: python -m weather.cli.main [run|status|report]")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

