from weather.strategy.scanner import build_outcomes, select_signal


def test_build_outcomes_parses_temperature_ranges():
    event = {
        "markets": [
            {
                "id": "1",
                "question": "Will the highest temperature in NYC be between 75-77°F on July 4?",
                "volume": 1200,
                "outcomePrices": "[0.08,0.92]",
            },
            {
                "id": "2",
                "question": "Invalid market",
                "volume": 100,
                "outcomePrices": "[0.50,0.50]",
            },
        ]
    }
    outcomes = build_outcomes(event)
    assert len(outcomes) == 1
    assert outcomes[0]["range"] == (75.0, 77.0)
    assert outcomes[0]["ask"] == 0.92


def test_select_signal_builds_entry_candidate():
    outcomes = [
        {
            "question": "Will the highest temperature in NYC be between 75-77°F on July 4?",
            "market_id": "1",
            "range": (75.0, 77.0),
            "bid": 0.08,
            "ask": 0.08,
            "price": 0.08,
            "spread": 0.01,
            "volume": 1200.0,
        }
    ]
    signal = select_signal(
        outcomes=outcomes,
        forecast_temp=76.0,
        sigma=2.0,
        best_source="ecmwf",
        opened_at="2026-03-22T00:00:00+00:00",
        balance=10000.0,
        min_volume=500.0,
        min_ev=0.1,
        kelly_fraction=0.25,
        max_bet=20.0,
    )
    assert signal is not None
    assert signal["market_id"] == "1"
    assert signal["forecast_src"] == "ecmwf"
    assert signal["cost"] == 20.0
