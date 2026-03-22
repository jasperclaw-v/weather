# CLAUDE.md

## Project Identity

This repository is an independent continuation of `alteregoeth-ai/weatherbot`.
It is being unforked into a new system named `weather`.

The current upstream scripts are migration sources, not the target architecture.
Do not keep expanding `bot_v2.py` as the primary implementation file.

## Primary Objective

Refactor the repository from monolithic scripts into a modular Python package for
weather-market research, paper trading, backtesting, and later live Polymarket
CLOB execution.

## Operating Rules

1. Read `SPEC.md` before making structural changes.
2. Preserve current behavior where practical until tests exist.
3. Do not make broad multi-file edits before identifying the migration source in
   `bot_v2.py`.
4. Separate strategy, data ingestion, persistence, and execution concerns.
5. Use typed models at module boundaries. Avoid passing raw dicts between new
   modules unless there is a temporary migration wrapper.
6. Keep new code ASCII unless an existing file requires otherwise.
7. Never hardcode secrets, API keys, wallet keys, or passphrases in tracked files.
8. Do not enable live order placement by default.

## Architecture Rules

- `weather/core` owns probability, EV, Kelly, shared types, and constants.
- `weather/data` owns station mapping, forecast adapters, snapshots, and storage.
- `weather/strategy` owns signal generation, sizing, calibration, and exits.
- `weather/execution` owns Polymarket auth, signing, routing, and live execution.
- `weather/ui` is read-only with respect to trading decisions.
- `weather/alerts` transports events but does not decide when to trade.
- `weather/backtests` replays persisted events and computes evaluation metrics.

No module may bypass these boundaries without a documented reason.

## Statistical Rules

- All temperature buckets must use Gaussian probability, including regular buckets.
- Exact-match buckets must be modeled as bounded intervals, not exact point masses.
- Sigma calibration must be based on residual dispersion, not MAE labeled as sigma.
- Kelly sizing must remain fractional. Default is quarter-Kelly unless explicitly
  changed in config and justified.
- EV calculations for execution must account for fees and slippage.

## Data Rules

- Airport station coordinates are the source of truth for market resolution.
- Every forecast snapshot must record source, station, timestamp, horizon, and
  value.
- Persist enough data to replay all entries, exits, and resolution outcomes.
- Keep storage schemas versionable once stabilized.

## Safety Rules

- Default all new execution paths to paper or dry-run mode.
- Live execution requires explicit configuration and dedicated tests.
- Avoid destructive git actions.
- Do not remove historical scripts until parity is proven.

## Testing Rules

Before changing financial or probabilistic logic:

- add or update tests first
- cover normal buckets, edge buckets, exact buckets, EV, Kelly, and calibration
  fallback behavior

Before changing execution code:

- add dry-run tests for auth headers, signatures, and serialized order payloads

Minimum target coverage for confidence:

- core math and calibration modules should be comprehensively unit tested

## Migration Order

1. Package skeleton and typed models
2. Core probability and finance extraction
3. Data/storage extraction
4. Strategy extraction and parity checks
5. Execution layer
6. Backtesting, dashboard, and alerts

Do not start with the dashboard or alerts.
Do not start with live CLOB execution.

## Working Style

- Prefer small, reviewable patches.
- Keep behavior-preserving moves separate from logic changes when possible.
- When a function from `bot_v2.py` is migrated, note the source in commit or patch
  context so parity can be checked quickly.
- If context grows too large, summarize progress in a markdown file before
  continuing.

## Document and Clear

When the active session becomes too context-heavy:

1. Write a short markdown progress note with:
   - completed steps
   - current architecture state
   - remaining blockers
   - exact next step
2. Clear the session.
3. Resume from the progress note plus `SPEC.md` and `CLAUDE.md`.

## Token Budget Guidance

Use effort where it matters:

- High attention:
  - `weather/core`
  - `weather/strategy`
  - `weather/execution`
- Medium attention:
  - `weather/data`
  - `weather/backtests`
- Lower attention:
  - `weather/ui`
  - `weather/alerts`

Do not spend large context budgets polishing UI or prose before the trading core
is correct.

## Near-Term Repo Cleanup

- Resolve the naming mismatch between README references to `weatherbet.py` and the
  actual `bot_v2.py`.
- Remove any tracked real or placeholder secrets from `config.json`.
- Add a proper dependency manifest and test tooling.

## First Task for Future Sessions

Start by creating the package skeleton, extracting the probability and finance
functions from `bot_v2.py`, and adding tests that lock in the corrected Gaussian
bucket behavior.
