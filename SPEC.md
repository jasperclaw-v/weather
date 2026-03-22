# Weather Codex Specification

## Purpose

This repository is an unforking and modernization of `alteregoeth-ai/weatherbot`.
The current upstream codebase is a compact prototype centered around two monolithic
scripts:

- `bot_v1.py`: simple paper-trading scanner
- `bot_v2.py`: current full prototype with forecasts, pricing, storage, sizing,
  calibration, and position management

The goal is to evolve that prototype into a modular, typed, testable system named
`weather` without losing the working logic that already exists.

This document is the implementation baseline. No large-scale refactor should begin
without following the migration order and acceptance criteria defined here.

## Current State

The upstream repository is small:

- `bot_v2.py` contains math, calibration, forecast adapters, Polymarket reads,
  JSON persistence, market scanning, reporting, and trade lifecycle logic in a
  single file of roughly 1000 lines.
- `bot_v1.py` is retained as a historical/simple version.
- `config.json` stores runtime parameters.
- `sim_dashboard_repost.html` is a static artifact, not an application module.

The current prototype already includes:

- Gaussian handling for edge buckets
- EV and Kelly sizing
- Per-city/source calibration persisted to JSON
- Multi-source forecasting via Open-Meteo, METAR, and Visual Crossing
- JSON market/state persistence
- Paper-trading entry, stop, trailing stop, and resolution logic

The current prototype does not include:

- A package/module architecture
- Type-safe models at module boundaries
- Unit or integration tests
- A Polymarket CLOB execution client
- EIP-712 signing and L2 auth
- A dedicated market-to-station mapping layer
- A true backtesting engine
- A Streamlit dashboard
- An alert bridge
- Operational documentation for agentic development

## Architecture Goals

The target system must:

1. Preserve working trading logic while decomposing it into modules.
2. Replace deterministic regular-bucket logic with Gaussian bucket probability for
   all bucket types.
3. Improve calibration so sigma is based on residual dispersion rather than MAE
   alone.
4. Separate strategy from execution.
5. Make every trading decision reproducible from persisted data.
6. Support both paper trading and live Polymarket CLOB execution.
7. Support offline replay and backtesting before real capital is used.

## Target Package Layout

```text
weather/
  __init__.py
  core/
    probability.py
    finance.py
    types.py
    constants.py
  data/
    mapping.py
    models/
      openmeteo.py
      ecmwf.py
      hrrr.py
      metar.py
      visualcrossing.py
    storage.py
    snapshots.py
  execution/
    polymarket.py
    auth.py
    signing.py
    router.py
  strategy/
    scanner.py
    sizing.py
    risk.py
    calibration.py
    take_profit.py
  backtests/
    engine.py
    metrics.py
    loaders.py
  ui/
    dashboard.py
  alerts/
    imessage.py
  cli/
    main.py
tests/
  test_probability.py
  test_finance.py
  test_calibration.py
  test_mapping.py
  test_polymarket_auth.py
  test_strategy.py
data/
  state.json
  calibration.json
  tp_schedule.json
  markets/
  replay/
```

## Source-to-Target Migration Map

The current `bot_v2.py` should be treated as source material and split as follows:

- Math and bucket logic:
  - from `bot_v2.py` functions `norm_cdf`, `bucket_prob`, `calc_ev`, `calc_kelly`,
    `bet_size`
  - into `weather/core/probability.py` and `weather/core/finance.py`

- Calibration:
  - from `load_cal`, `get_sigma`, `run_calibration`
  - into `weather/strategy/calibration.py`

- Forecast adapters:
  - from `get_ecmwf`, `get_hrrr`, `get_metar`, `get_actual_temp`
  - into `weather/data/models/*.py`

- Polymarket reads and parsing:
  - from `get_polymarket_event`, `get_market_price`, `parse_temp_range`,
    `hours_to_resolution`
  - into `weather/execution/polymarket.py` and `weather/data/mapping.py`

- Persistence:
  - from `market_path`, `load_market`, `save_market`, `load_all_markets`,
    `load_state`, `save_state`
  - into `weather/data/storage.py`

- Forecast snapshots:
  - from `take_forecast_snapshot`
  - into `weather/data/snapshots.py`

- Strategy loop:
  - from `scan_and_update` and position-management sections
  - into `weather/strategy/scanner.py`, `weather/strategy/risk.py`,
    `weather/strategy/sizing.py`

- CLI/reporting:
  - from `print_status`, `print_report`, `monitor_positions`, `run_loop`
  - into `weather/cli/main.py`

`bot_v1.py` should remain untouched initially except for archival or explicit
compatibility decisions.

## Domain Model

Before broad refactoring, introduce typed models. Dataclasses are sufficient to
start; Pydantic is optional.

Required entities:

- `Location`
- `WeatherBucket`
- `ForecastSnapshot`
- `MarketQuote`
- `MarketRecord`
- `Position`
- `CalibrationRecord`
- `OrderIntent`
- `OrderFill`
- `PortfolioState`

Requirements:

- Modules must exchange typed objects rather than ad hoc dicts.
- Serialization should remain JSON-compatible.
- Persisted records must retain source, timestamp, market id, station, and horizon.

## Statistical Specification

### Bucket Probability

The legacy flaw in `bot_v2.py` is here:

- edge buckets use a Gaussian CDF
- regular buckets still use deterministic membership via `in_bucket`

Target behavior:

```text
P(low < X <= high) = Phi((high - mu) / sigma) - Phi((low - mu) / sigma)
```

Implementation requirements:

- Use Gaussian logic for regular buckets, edge buckets, and exact buckets.
- Exact buckets should be modeled as a bounded interval around the exact value.
- Keep Fahrenheit and Celsius defaults only as fallbacks.
- Sigma must come from calibration whenever enough history exists.

### EV and Kelly

Current EV and Kelly formulas exist but are too idealized for live execution.

Target behavior:

- compute EV from estimated fill price, not only displayed ask
- include taker fee and slippage assumptions
- keep default `KELLY_FRACTION = 0.25`
- clamp position size conservatively

Required outputs:

- raw probability
- fee-adjusted EV
- Kelly fraction
- recommended notional size

### Calibration

Current calibration stores MAE as `sigma`. That is directionally useful but
statistically incorrect.

Target behavior:

- compute residuals as `forecast - actual`
- derive sigma from residual standard deviation or robust equivalent
- calibrate by `(city, source, horizon bucket)` when data is sufficient
- retain fallback to coarser grouping when sample size is low

Calibration acceptance criteria:

- no calibration update when sample size is below threshold
- persisted output includes sigma, sample size, method, timestamp
- tests cover fallback behavior

## Forecast Data Layer

### Station Mapping

Airport station coordinates are the resolution source of truth.

Requirements:

- create a dedicated mapping module rather than embedding station metadata inside
  the trading loop
- support current known stations from upstream
- allow future per-market overrides if Polymarket changes resolution language

### Forecast Sources

Short-term implementation:

- preserve current Open-Meteo-backed ECMWF/HRLRR logic as adapters
- preserve METAR live observation ingestion
- preserve Visual Crossing actual temperature lookup for resolution

Future implementation:

- add direct ECMWF/HRRR ingestion only after modularization and test coverage

Important note:

- `bot_v2.py` labels US short-range data as HRRR while calling the
  `gfs_seamless` Open-Meteo model. This mismatch must be corrected in naming or
  replaced with a true HRRR source before claiming HRRR support.

## Execution Layer

The current repo reads Gamma market data but does not execute via the CLOB.

The execution layer must be introduced only after core math and types are
stabilized.

Required capabilities:

- Polymarket L2 authenticated requests
- HMAC-SHA256 request signing
- EIP-712 local signing for orders
- support for GTC, GTD, and FOK or equivalent supported order policies
- estimate-fill or book-based slippage checks before routing
- allowance/preflight checks for buy and sell flows

Design constraint:

- strategy modules produce `OrderIntent`
- execution modules decide how to serialize and route it

## Persistence and Replay

Existing per-market JSON storage should be preserved conceptually but normalized.

Requirements:

- keep append-only forecast and market snapshot history
- persist every position transition
- ensure data is sufficient to replay entry, exit, and resolution behavior
- keep storage format versioned once schema stabilizes

## Backtesting

Backtesting should be event-driven and data-first.

Phase 1:

- replay persisted market records and forecast snapshots
- evaluate entry timing, exits, and sizing logic

Phase 2:

- optionally integrate `Backtesting.py` if it adds value after the event model is
  stable

Metrics:

- Brier score
- PnL
- max drawdown
- Sharpe ratio
- Sortino ratio
- calibration error by city/source/horizon

## Dashboard and Alerts

These are downstream of the core refactor.

Dashboard requirements:

- separate read-only surveillance from trading logic
- show portfolio state, open positions, calibration state, forecast divergence,
  and market-price convergence

Alert requirements:

- send execution and risk events only
- do not embed trading logic inside alert transport
- use an explicit adapter for macOS `osascript`

## Delivery Phases

### Phase 0: Unfork and Baseline

- Treat this repo as an independent codebase, not a fork workflow.
- Add `SPEC.md` and `CLAUDE.md`.
- Freeze the upstream scripts as migration sources.

Acceptance:

- repository remains runnable in its current form
- spec approved before deep refactor

### Phase 1: Package Skeleton and Types

- create package layout
- add typed models
- move config/constants into stable modules
- add test harness

Acceptance:

- imports work
- tests run
- no behavior change required yet

### Phase 2: Statistical Core Extraction

- extract probability and finance logic
- convert all bucket logic to Gaussian
- add test coverage for regular, edge, and exact buckets

Acceptance:

- deterministic tests reproduce expected bucket probabilities
- EV and Kelly tests pass

### Phase 3: Data Layer Extraction

- split forecast adapters
- add storage abstraction
- move mapping into dedicated module

Acceptance:

- one command can fetch a forecast snapshot and serialize it through typed models

### Phase 4: Strategy Extraction

- break `scan_and_update` into scanner, sizing, and risk components
- keep paper-trading mode working

Acceptance:

- paper scan loop works through new modules
- old script can be deprecated after parity verification

### Phase 5: CLOB Execution

- add auth/signing/router modules
- introduce paper/live execution interface

Acceptance:

- dry-run execution integration tests pass
- no live order placement until explicit user approval

### Phase 6: Backtesting, Dashboard, Alerts

- build replay engine
- add Streamlit dashboard
- add iMessage bridge

Acceptance:

- replay metrics can be generated from stored data
- dashboard can render from local state without mutating it

## Risks and Constraints

- The upstream repo has no tests, so parity claims must be verified incrementally.
- The upstream README references `weatherbet.py`, but the file in repo is
  `bot_v2.py`. This naming inconsistency should be resolved early.
- Current config includes a live-looking API key value in `config.json`; secrets
  should be removed from tracked config before any public push.
- The current prototype uses raw dicts everywhere; direct broad edits without a
  type layer will create regressions.
- Polymarket execution APIs and auth details are operationally sensitive and
  should be implemented behind explicit dry-run guards.

## Definition of Done

This refactor is complete when:

- the system is packaged and typed
- the statistical engine uses Gaussian probabilities for all bucket types
- sigma calibration is statistically grounded
- strategy and execution are cleanly separated
- paper trading and replay are both supported
- CLOB execution exists behind safe controls
- tests cover core financial and probabilistic logic
- dashboard and alerting operate from persisted state

## Immediate Next Step

The next implementation step after approving this document is:

1. Create the package skeleton and test harness.
2. Move probability, EV, and Kelly logic into `weather/core`.
3. Add tests that lock in corrected Gaussian behavior before changing the scanner.
