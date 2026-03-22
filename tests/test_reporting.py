import io
from contextlib import redirect_stdout

from weather.reporting import print_full_report, print_status_report


def test_print_status_report_emits_header():
    output = io.StringIO()
    with redirect_stdout(output):
        print_status_report(
            state={"balance": 100.0, "starting_balance": 100.0, "wins": 0, "losses": 0},
            markets=[],
            find_outcome_price=lambda outcomes, market_id, side="price": None,
        )
    assert "WEATHERBET" in output.getvalue()


def test_print_full_report_handles_empty_resolved():
    output = io.StringIO()
    with redirect_stdout(output):
        print_full_report(resolved=[], locations={})
    assert "No resolved markets yet." in output.getvalue()
