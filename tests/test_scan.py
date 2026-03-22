from weather.scan import format_paper_scan_report


def test_format_paper_scan_report_is_json():
    output = format_paper_scan_report(
        {
            "filters": {"max_price": 0.9, "max_slippage": 0.4},
            "scan_result": {"new": 2, "closed": 0, "resolved": 0},
            "positions": [],
        }
    )
    assert '"max_price": 0.9' in output
    assert '"new": 2' in output
