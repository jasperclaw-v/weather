"""Compatibility entrypoint matching the README command."""

from weather.cli.main import main


if __name__ == "__main__":
    raise SystemExit(main())

