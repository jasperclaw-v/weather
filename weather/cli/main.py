"""CLI entrypoint for the package-owned runtime."""

import sys

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
    else:
        print("Usage: python -m weather.cli.main [run|status|report]")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
