from weather.strategy.calibration import get_sigma, run_sigma_calibration


def test_get_sigma_falls_back_to_city_default():
    assert get_sigma("nyc", "ecmwf", calibration={}) == 2.0


def test_run_sigma_calibration_uses_residual_stddev():
    markets = [
        {
            "city": "nyc",
            "status": "resolved",
            "actual_temp": 80.0,
            "forecast_snapshots": [{"ecmwf": 79.0}],
        },
        {
            "city": "nyc",
            "status": "resolved",
            "actual_temp": 82.0,
            "forecast_snapshots": [{"ecmwf": 84.0}],
        },
        {
            "city": "nyc",
            "status": "resolved",
            "actual_temp": 78.0,
            "forecast_snapshots": [{"ecmwf": 77.0}],
        },
    ]
    calibration = run_sigma_calibration(markets, calibration_min=3)
    sigma = calibration["nyc_ecmwf"]["sigma"]
    assert round(sigma, 3) == 1.414
