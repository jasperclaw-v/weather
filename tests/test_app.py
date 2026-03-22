from weather.app import RuntimeConfig, build_runtime_context, runtime_locations


def test_runtime_locations_include_nyc():
    locations = runtime_locations()
    assert locations["nyc"]["station"] == "KLGA"


def test_build_runtime_context_exposes_configured_thresholds():
    context = build_runtime_context(
        locations={"nyc": {"name": "New York City"}},
        config=RuntimeConfig(min_ev=0.25, max_bet=50.0),
        sleep=lambda _: None,
        load_state=lambda: {},
        save_state=lambda state: None,
        load_market=lambda city, date: {},
        save_market=lambda market: None,
        load_all_markets=lambda: [],
        new_market=lambda city, date, event, hours: {},
        take_forecast_snapshot=lambda city, dates: {},
        get_polymarket_event=lambda city, month, day, year: None,
        hours_to_resolution=lambda end_date: 0.0,
        build_outcomes=lambda event: [],
        apply_stop_and_forecast_exits=lambda **kwargs: ({}, 0.0, 0, None),
        get_sigma=lambda city, source: 2.0,
        select_signal=lambda **kwargs: None,
        refresh_signal_with_live_quotes=lambda signal, **kwargs: (signal, None),
        check_market_resolved=lambda market_id: None,
        apply_resolution=lambda market, won, ts=None: (market, 0.0, "win"),
        run_calibration=lambda markets: {},
        set_calibration=lambda cal: None,
        apply_monitor_exit=lambda **kwargs: ({}, 0, None),
    )
    assert context.MIN_EV == 0.25
    assert context.MAX_BET == 50.0
