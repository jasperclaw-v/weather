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
