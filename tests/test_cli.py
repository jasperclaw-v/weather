import io
from contextlib import redirect_stdout

from weather.cli.main import main


def test_cli_status_command_runs():
    output = io.StringIO()
    with redirect_stdout(output):
        rc = main(["status"])
    assert rc == 0
    assert "WEATHERBET" in output.getvalue()


def test_cli_report_command_runs():
    output = io.StringIO()
    with redirect_stdout(output):
        rc = main(["report"])
    assert rc == 0
    assert "FULL REPORT" in output.getvalue()


def test_cli_backtest_command_runs():
    output = io.StringIO()
    with redirect_stdout(output):
        rc = main(["backtest"])
    assert rc == 0
    assert '"n_trades"' in output.getvalue()


def test_cli_scan_command_runs(monkeypatch):
    monkeypatch.setattr(
        "weather.cli.main.run_paper_scan",
        lambda max_price=None, max_slippage=None: {"scan_result": {"new": 1}, "positions": []},
    )
    monkeypatch.setattr(
        "weather.cli.main.format_paper_scan_report",
        lambda report: "scan-report",
    )
    output = io.StringIO()
    with redirect_stdout(output):
        rc = main(["scan", "0.9", "0.4"])
    assert rc == 0
    assert "scan-report" in output.getvalue()
