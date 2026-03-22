from weather.strategy.risk import evaluate_position


def test_take_profit_closes_position():
    result = evaluate_position(
        entry_price=0.2,
        current_price=0.8,
        shares=100,
        hours_left=72,
    )
    assert result.action == "close"
    assert result.reason == "take_profit"


def test_forecast_drift_closes_position():
    result = evaluate_position(
        entry_price=0.2,
        current_price=0.25,
        shares=100,
        hours_left=12,
        forecast_temp=80,
        bucket_low=75,
        bucket_high=77,
        unit="F",
    )
    assert result.action == "close"
    assert result.reason == "forecast_changed"

