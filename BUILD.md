# Build Guide

This project is a Python package with optional UI extras. The current repo supports:

- core scan / monitor runtime
- isolated paper scans against live APIs
- backtest replay over stored markets
- Streamlit dashboard

## Prerequisites

- Python `3.9+`
- `pip`
- network access for live API scans

## Clone

```bash
git clone https://github.com/jasperclaw-v/weather.git
cd weather
```

## Install

Minimal runtime:

```bash
python3 -m pip install -e .
```

Runtime + tests:

```bash
python3 -m pip install -e '.[dev]'
```

Runtime + dashboard:

```bash
python3 -m pip install -e '.[ui]'
```

Full local developer setup:

```bash
python3 -m pip install -e '.[dev,ui,calibration]'
```

Fallback install using the pinned requirements file:

```bash
python3 -m pip install -r requirements.txt
```

## Configuration

Create or edit `config.json` in the repo root:

```json
{
  "balance": 10000.0,
  "max_bet": 20.0,
  "min_ev": 0.1,
  "max_price": 0.45,
  "min_volume": 500,
  "min_hours": 2.0,
  "max_hours": 72.0,
  "kelly_fraction": 0.25,
  "scan_interval": 3600,
  "calibration_min": 30,
  "vc_key": "",
  "max_slippage": 0.03
}
```

For Polymarket execution wiring, set env vars from `.env.example` when needed. The system is still dry-run by default unless you explicitly enable live routing in your environment.

## Verify The Build

Bytecode compile:

```bash
python3 -m py_compile bot_v2.py weather/**/*.py
```

Run the full test suite:

```bash
PYTHONPATH=. python3 -m pytest -q
```

## Run The App

Compatibility entrypoint:

```bash
python3 weatherbet.py
```

Package CLI:

```bash
python3 -m weather.cli.main
```

Status:

```bash
python3 weatherbet.py status
```

Resolved-market report:

```bash
python3 weatherbet.py report
```

Backtest replay:

```bash
python3 weatherbet.py backtest
```

## Run A Live Paper Scan

Default filters from `config.json`:

```bash
python3 weatherbet.py scan
```

Override filters for a one-shot isolated scan:

```bash
python3 weatherbet.py scan 0.9 0.4
```

This does not mutate your main saved trading state. It runs in a temporary data directory and returns JSON containing:

- `filters`
- `log`
- `scan_result`
- `positions`

## Launch The Dashboard

Install UI deps first:

```bash
python3 -m pip install -e '.[ui]'
```

Then launch either way:

```bash
python3 weatherbet.py dashboard
```

or:

```bash
python3 -m streamlit run weather/ui/dashboard.py
```

The dashboard shows:

- balance and high-level portfolio stats
- open positions
- resolved-market table
- replay equity curve
- live paper-scan buys and skips

## Project Layout

Key modules:

- `weather/runtime.py`: runtime shell
- `weather/engine.py`: scan / monitor execution flow
- `weather/scan.py`: isolated live paper scans
- `weather/backtests/`: replay metrics
- `weather/execution/`: dry-run execution and Polymarket routing
- `weather/ui/dashboard.py`: Streamlit monitoring view
- `tests/`: test suite

## Common Issues

`streamlit: No module named streamlit`

Install UI extras:

```bash
python3 -m pip install -e '.[ui]'
```

`ModuleNotFoundError` when running tests

Run tests from the repo root:

```bash
PYTHONPATH=. python3 -m pytest -q
```

No positions appear in `scan`

That usually means the live ask, spread, or EV filters rejected the trades. Run a looser paper scan:

```bash
python3 weatherbet.py scan 0.9 0.4
```
