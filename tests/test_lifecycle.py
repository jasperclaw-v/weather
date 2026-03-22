from weather.strategy.lifecycle import apply_monitor_exit, apply_resolution, apply_stop_and_forecast_exits


def test_apply_resolution_marks_market_resolved():
    market = {
        "position": {"entry_price": 0.2, "cost": 20.0, "shares": 100.0, "status": "open"},
        "status": "open",
    }
    updated, credit, outcome = apply_resolution(market, won=True, ts="2026-03-22T00:00:00+00:00")
    assert updated["status"] == "resolved"
    assert updated["position"]["status"] == "closed"
    assert credit == 100.0
    assert outcome == "win"


def test_apply_stop_and_forecast_exit_closes_on_forecast_change():
    market = {
        "unit": "F",
        "position": {
            "market_id": "1",
            "entry_price": 0.2,
            "cost": 20.0,
            "shares": 100.0,
            "bucket_low": 75.0,
            "bucket_high": 77.0,
            "status": "open",
        },
    }
    outcomes = [{"market_id": "1", "bid": 0.25, "price": 0.25}]
    updated, balance, count, reason = apply_stop_and_forecast_exits(
        market,
        outcomes,
        forecast_temp=80.0,
        balance=100.0,
        ts="2026-03-22T00:00:00+00:00",
    )
    assert updated["position"]["status"] == "closed"
    assert balance == 125.0
    assert count == 1
    assert reason == "CLOSE"


def test_apply_monitor_exit_takes_profit():
    market = {
        "position": {
            "entry_price": 0.2,
            "shares": 100.0,
            "status": "open",
        }
    }
    updated, count, reason = apply_monitor_exit(
        market,
        current_price=0.8,
        hours_left=72.0,
        schedule=[{"hours_min": 48, "hours_max": 9999, "threshold": 0.75}],
    )
    assert updated["position"]["status"] == "closed"
    assert count == 1
    assert reason == "TAKE"
