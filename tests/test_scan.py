from weather import scan as scan_mod
from weather.scan import format_paper_scan_report


def test_format_paper_scan_report_is_json():
    output = format_paper_scan_report(
        {
            "filters": {"max_price": 0.9, "max_slippage": 0.4},
            "log": ["[BUY] sample"],
            "scan_result": {"new": 2, "closed": 0, "resolved": 0},
            "positions": [],
        }
    )
    assert '"max_price": 0.9' in output
    assert '"new": 2' in output


def test_run_paper_scan_captures_log(monkeypatch):
    class DummyContext:
        def __enter__(self):
            return None

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(scan_mod, "isolated_scan_environment", lambda max_price=None, max_slippage=None: DummyContext())
    monkeypatch.setattr(scan_mod.runtime, "load_cal", lambda: {})
    monkeypatch.setattr(scan_mod.runtime, "MAX_PRICE", 0.9)
    monkeypatch.setattr(scan_mod.runtime, "MAX_SLIPPAGE", 0.4)
    monkeypatch.setattr(
        scan_mod.storage,
        "load_all_markets",
        lambda: [
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
            }
        ],
    )

    def fake_scan_and_update():
        print("  [BUY]  New York City D+1 2026-03-23 | -999.0-51.0F | $0.800 | EV +0.13 | $20.00 (HRRR)")
        return (1, 0, 0)

    monkeypatch.setattr(scan_mod.runtime, "scan_and_update", fake_scan_and_update)

    report = scan_mod.run_paper_scan(max_price=0.9, max_slippage=0.4)

    assert "[BUY]" in report["log"][0]
    assert report["scan_result"]["new"] == 1
