from weather.ui.dashboard import (
    build_open_positions_rows,
    build_trade_history_rows,
    extract_scan_events,
)


def test_extract_scan_events_parses_buy_skip_and_warn():
    events = extract_scan_events(
        [
            "  [BUY]  New York City D+1 2026-03-23 | -999.0-51.0F | $0.800 | EV +0.13 | $20.00 (HRRR)",
            "  [SKIP] Lucknow 2026-03-23 — live EV -0.20 below min 0.10",
            "  [WARN] Could not fetch real ask for abc: timeout",
        ]
    )

    assert events[0]["type"] == "buy"
    assert events[0]["city"] == "New York City"
    assert events[0]["entry_price"] == 0.8
    assert events[1]["type"] == "skip"
    assert events[1]["detail"] == "live EV -0.20 below min 0.10"
    assert events[2]["type"] == "warn"


def test_build_open_positions_rows_filters_to_open_positions():
    markets = [
        {
            "city_name": "New York City",
            "date": "2026-03-23",
            "unit": "F",
            "position": {
                "status": "open",
                "bucket_low": -999.0,
                "bucket_high": 51.0,
                "entry_price": 0.8,
                "shares": 25.0,
                "cost": 20.0,
                "ev": 0.13,
                "p": 0.93,
                "forecast_src": "hrrr",
            },
        },
        {
            "city_name": "Toronto",
            "date": "2026-03-25",
            "unit": "C",
            "position": {
                "status": "closed",
                "bucket_low": 10.0,
                "bucket_high": 999.0,
                "entry_price": 0.42,
                "shares": 46.95,
                "cost": 20.0,
            },
        },
    ]

    rows = build_open_positions_rows(markets)

    assert rows == [
        {
            "city": "New York City",
            "date": "2026-03-23",
            "bucket": "-999.0-51.0F",
            "entry_price": 0.8,
            "shares": 25.0,
            "cost": 20.0,
            "ev": 0.13,
            "probability": 0.93,
            "source": "hrrr",
        }
    ]


def test_build_trade_history_rows_accumulates_equity():
    rows = build_trade_history_rows(
        {
            "trades": [
                {"city": "nyc", "date": "2026-03-23", "pnl": 5.0, "probability": 0.7, "outcome": 1},
                {"city": "toronto", "date": "2026-03-25", "pnl": -2.0, "probability": 0.6, "outcome": 0},
            ]
        }
    )

    assert rows[0]["equity_pnl"] == 5.0
    assert rows[1]["equity_pnl"] == 3.0
