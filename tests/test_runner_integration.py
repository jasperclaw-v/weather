from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from weather.data import storage
from weather import engine
from weather import runtime


def configure_temp_storage(monkeypatch, tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    markets_dir = data_dir / "markets"
    calibration_file = data_dir / "calibration.json"
    state_file = data_dir / "state.json"
    tp_file = data_dir / "tp_schedule.json"

    monkeypatch.setattr(storage, "DATA_DIR", data_dir)
    monkeypatch.setattr(storage, "MARKETS_DIR", markets_dir)
    monkeypatch.setattr(storage, "CALIBRATION_FILE", calibration_file)
    monkeypatch.setattr(storage, "STATE_FILE", state_file)
    monkeypatch.setattr(storage, "TP_FILE", tp_file)

    monkeypatch.setattr(runtime, "DATA_DIR", data_dir)
    monkeypatch.setattr(runtime, "MARKETS_DIR", markets_dir)


class FixedDateTime(datetime):
    @classmethod
    def now(cls, tz=None):
        fixed = cls(2026, 3, 22, 12, 0, 0, tzinfo=timezone.utc)
        if tz is None:
            return fixed.replace(tzinfo=None)
        return fixed.astimezone(tz)


def pin_engine_now(monkeypatch) -> None:
    monkeypatch.setattr(engine, "datetime", FixedDateTime)


def test_scan_and_update_opens_position(monkeypatch, tmp_path):
    configure_temp_storage(monkeypatch, tmp_path)

    def fake_snapshots(city_slug, dates):
        return {
            dates[0]: {
                "ts": "2026-03-22T00:00:00+00:00",
                "ecmwf": 76.0,
                "hrrr": 76.0,
                "metar": None,
                "best": 76.0,
                "best_source": "ecmwf",
            }
        }

    def fake_event(city_slug, month, day, year):
        if city_slug != "nyc" or day != 22 or month != "march" or year != 2026:
            return None
        return {
            "endDate": "2026-03-23T00:00:00Z",
            "markets": [
                {
                    "id": "m1",
                    "question": "Will the highest temperature in nyc be between 75-77°F on March 22 2026?",
                    "volume": 1500,
                    "outcomePrices": "[0.08,0.09]",
                }
            ],
        }

    ctx = SimpleNamespace(
        LOCATIONS={"nyc": runtime.LOCATIONS["nyc"]},
        MONTHS=runtime.runtime_context().MONTHS,
        MIN_HOURS=2.0,
        MAX_HOURS=72.0,
        MIN_VOLUME=500,
        MIN_EV=0.10,
        KELLY_FRACTION=0.25,
        MAX_BET=20.0,
        MAX_SLIPPAGE=0.03,
        MAX_PRICE=0.45,
        CALIBRATION_MIN=30,
        DEFAULT_TP_SCHEDULE=runtime.DEFAULT_TP_SCHEDULE,
        requests=runtime.requests,
        sleep=lambda _: None,
        load_state=runtime.load_state,
        save_state=runtime.save_state,
        load_market=storage.load_market,
        save_market=storage.save_market,
        load_all_markets=storage.load_all_markets,
        new_market=lambda city_slug, date_str, event, hours: storage.new_market_record(
            city_slug, runtime.LOCATIONS[city_slug], date_str, event, hours
        ),
        take_forecast_snapshot=fake_snapshots,
        get_polymarket_event=fake_event,
        hours_to_resolution=lambda _: 12.0,
        build_outcomes=runtime.build_outcomes,
        apply_stop_and_forecast_exits=lambda market, outcomes, forecast_temp, balance, ts: (market, balance, 0, None),
        get_sigma=lambda city_slug, source="ecmwf": 2.0,
        select_signal=lambda **kwargs: {
            "market_id": "m1",
            "question": "Will the highest temperature in nyc be between 75-77°F on March 22 2026?",
            "bucket_low": 75.0,
            "bucket_high": 77.0,
            "entry_price": 0.09,
            "bid_at_entry": 0.08,
            "spread": 0.01,
            "shares": 222.22,
            "cost": 20.0,
            "p": 0.38,
            "ev": 0.29,
            "kelly": 0.06,
            "forecast_temp": 76.0,
            "forecast_src": "ecmwf",
            "sigma": 2.0,
            "opened_at": "2026-03-22T00:00:00+00:00",
            "status": "open",
            "pnl": None,
            "exit_price": None,
            "close_reason": None,
            "closed_at": None,
        },
        refresh_signal_with_live_quotes=lambda signal, max_slippage, max_price: (signal, None),
        check_market_resolved=lambda market_id: None,
        apply_resolution=runtime.apply_resolution,
        run_calibration=lambda markets: {},
        set_calibration=lambda value: None,
        apply_monitor_exit=runtime.apply_monitor_exit,
        execution_service=None,
    )
    monkeypatch.setattr(runtime, "runtime_context", lambda: ctx)

    new_pos, closed, resolved = runtime.scan_and_update()

    assert new_pos == 1
    assert closed == 0
    assert resolved == 0
    markets = storage.load_all_markets()
    assert len(markets) == 1
    assert markets[0]["position"]["status"] == "open"


def test_monitor_positions_closes_position(monkeypatch, tmp_path):
    configure_temp_storage(monkeypatch, tmp_path)
    storage.save_state(
        {
            "balance": 100.0,
            "starting_balance": 100.0,
            "total_trades": 1,
            "wins": 0,
            "losses": 0,
            "peak_balance": 100.0,
        }
    )
    storage.save_market(
        {
            "city": "nyc",
            "city_name": "New York City",
            "date": "2026-03-22",
            "unit": "F",
            "station": "KLGA",
            "event_end_date": "2026-03-25T00:00:00Z",
            "status": "open",
            "position": {
                "market_id": "m1",
                "entry_price": 0.2,
                "cost": 20.0,
                "shares": 100.0,
                "status": "open",
            },
            "all_outcomes": [{"market_id": "m1", "bid": 0.8, "price": 0.8}],
            "forecast_snapshots": [],
            "market_snapshots": [],
        }
    )

    class FakeResponse:
        def json(self):
            return {}

    monkeypatch.setattr(runtime.requests, "get", lambda *args, **kwargs: FakeResponse())

    closed = runtime.monitor_positions()

    assert closed == 1
    updated = storage.load_all_markets()[0]
    assert updated["position"]["status"] == "closed"


def test_scan_and_update_resolves_existing_market(monkeypatch, tmp_path):
    configure_temp_storage(monkeypatch, tmp_path)
    pin_engine_now(monkeypatch)
    storage.save_state(
        {
            "balance": 100.0,
            "starting_balance": 100.0,
            "total_trades": 1,
            "wins": 0,
            "losses": 0,
            "peak_balance": 100.0,
        }
    )
    storage.save_market(
        {
            "city": "nyc",
            "city_name": "New York City",
            "date": "2026-03-22",
            "unit": "F",
            "station": "KLGA",
            "event_end_date": "2026-03-22T12:00:00Z",
            "status": "open",
            "position": {
                "market_id": "m1",
                "entry_price": 0.2,
                "cost": 20.0,
                "shares": 100.0,
                "status": "open",
            },
            "all_outcomes": [],
            "forecast_snapshots": [],
            "market_snapshots": [],
        }
    )

    monkeypatch.setattr(runtime, "get_polymarket_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(runtime, "check_market_resolved", lambda market_id: True)
    monkeypatch.setattr(runtime.time, "sleep", lambda _: None)

    new_pos, closed, resolved = runtime.scan_and_update()

    assert new_pos == 0
    assert closed == 0
    assert resolved == 1
    updated = storage.load_all_markets()[0]
    assert updated["status"] == "resolved"


def test_scan_and_update_skips_after_live_ev_turns_negative(monkeypatch, tmp_path):
    configure_temp_storage(monkeypatch, tmp_path)
    pin_engine_now(monkeypatch)

    def fake_snapshots(city_slug, dates):
        return {
            dates[0]: {
                "ts": "2026-03-22T00:00:00+00:00",
                "ecmwf": 76.0,
                "hrrr": 76.0,
                "metar": None,
                "best": 76.0,
                "best_source": "ecmwf",
            }
        }

    def fake_event(city_slug, month, day, year):
        if city_slug != "nyc" or day != 22 or month != "march" or year != 2026:
            return None
        return {
            "endDate": "2026-03-23T00:00:00Z",
            "markets": [
                {
                    "id": "m1",
                    "question": "Will the highest temperature in nyc be between 75-77°F on March 22 2026?",
                    "volume": 1500,
                    "outcomePrices": "[0.08,0.09]",
                }
            ],
        }

    def fake_refresh(signal, max_slippage, max_price):
        updated = signal.copy()
        updated["entry_price"] = 0.95
        updated["spread"] = 0.01
        updated["shares"] = round(updated["cost"] / updated["entry_price"], 2)
        updated["ev"] = -0.10
        return updated, None

    monkeypatch.setattr(runtime, "take_forecast_snapshot", fake_snapshots)
    monkeypatch.setattr(runtime, "get_polymarket_event", fake_event)
    monkeypatch.setattr(runtime, "refresh_signal_with_live_quotes", fake_refresh)
    monkeypatch.setattr(runtime, "check_market_resolved", lambda market_id: None)
    monkeypatch.setattr(runtime.time, "sleep", lambda _: None)
    monkeypatch.setattr(runtime, "MAX_PRICE", 1.0)
    monkeypatch.setattr(runtime.CONFIG, "max_price", 1.0)

    new_pos, closed, resolved = runtime.scan_and_update()

    assert new_pos == 0
    assert closed == 0
    assert resolved == 0
