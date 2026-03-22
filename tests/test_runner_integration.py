from pathlib import Path

import bot_v2
from weather.data import storage


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

    monkeypatch.setattr(bot_v2, "DATA_DIR", data_dir)
    monkeypatch.setattr(bot_v2, "MARKETS_DIR", markets_dir)
    monkeypatch.setattr(bot_v2, "CALIBRATION_FILE", calibration_file)
    monkeypatch.setattr(bot_v2, "STATE_FILE", state_file)


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

    monkeypatch.setattr(bot_v2, "take_forecast_snapshot", fake_snapshots)
    monkeypatch.setattr(bot_v2, "get_polymarket_event", fake_event)
    monkeypatch.setattr(bot_v2, "refresh_signal_with_live_quotes", lambda signal, max_slippage, max_price: (signal, None))
    monkeypatch.setattr(bot_v2, "check_market_resolved", lambda market_id: None)
    monkeypatch.setattr(bot_v2.time, "sleep", lambda _: None)

    new_pos, closed, resolved = bot_v2.scan_and_update()

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

    monkeypatch.setattr(bot_v2.requests, "get", lambda *args, **kwargs: FakeResponse())

    closed = bot_v2.monitor_positions()

    assert closed == 1
    updated = storage.load_all_markets()[0]
    assert updated["position"]["status"] == "closed"


def test_scan_and_update_resolves_existing_market(monkeypatch, tmp_path):
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

    monkeypatch.setattr(bot_v2, "get_polymarket_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(bot_v2, "check_market_resolved", lambda market_id: True)
    monkeypatch.setattr(bot_v2.time, "sleep", lambda _: None)

    new_pos, closed, resolved = bot_v2.scan_and_update()

    assert new_pos == 0
    assert closed == 0
    assert resolved == 1
    updated = storage.load_all_markets()[0]
    assert updated["status"] == "resolved"
