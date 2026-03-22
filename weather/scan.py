"""One-shot paper scan helpers that do not mutate the main saved state."""

import json
import io
import tempfile
from contextlib import contextmanager
from contextlib import redirect_stdout
from pathlib import Path
from typing import Dict, Iterator, Optional

from weather import runtime
from weather.data import storage
@contextmanager
def isolated_scan_environment(max_price: Optional[float] = None, max_slippage: Optional[float] = None) -> Iterator[None]:
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp) / "data"
        markets_dir = data_dir / "markets"
        calibration_file = data_dir / "calibration.json"
        state_file = data_dir / "state.json"
        tp_file = data_dir / "tp_schedule.json"

        original = {
            "storage_DATA_DIR": storage.DATA_DIR,
            "storage_MARKETS_DIR": storage.MARKETS_DIR,
            "storage_CALIBRATION_FILE": storage.CALIBRATION_FILE,
            "storage_STATE_FILE": storage.STATE_FILE,
            "storage_TP_FILE": storage.TP_FILE,
            "runtime_DATA_DIR": runtime.DATA_DIR,
            "runtime_MARKETS_DIR": runtime.MARKETS_DIR,
            "runtime_MAX_PRICE": runtime.MAX_PRICE,
            "runtime_MAX_SLIPPAGE": runtime.MAX_SLIPPAGE,
            "config_max_price": runtime.CONFIG.max_price,
            "config_max_slippage": runtime.CONFIG.max_slippage,
        }

        storage.DATA_DIR = data_dir
        storage.MARKETS_DIR = markets_dir
        storage.CALIBRATION_FILE = calibration_file
        storage.STATE_FILE = state_file
        storage.TP_FILE = tp_file

        runtime.DATA_DIR = data_dir
        runtime.MARKETS_DIR = markets_dir
        if max_price is not None:
            runtime.MAX_PRICE = max_price
            runtime.CONFIG.max_price = max_price
        if max_slippage is not None:
            runtime.MAX_SLIPPAGE = max_slippage
            runtime.CONFIG.max_slippage = max_slippage

        try:
            yield
        finally:
            storage.DATA_DIR = original["storage_DATA_DIR"]
            storage.MARKETS_DIR = original["storage_MARKETS_DIR"]
            storage.CALIBRATION_FILE = original["storage_CALIBRATION_FILE"]
            storage.STATE_FILE = original["storage_STATE_FILE"]
            storage.TP_FILE = original["storage_TP_FILE"]

            runtime.DATA_DIR = original["runtime_DATA_DIR"]
            runtime.MARKETS_DIR = original["runtime_MARKETS_DIR"]
            runtime.MAX_PRICE = original["runtime_MAX_PRICE"]
            runtime.MAX_SLIPPAGE = original["runtime_MAX_SLIPPAGE"]
            runtime.CONFIG.max_price = original["config_max_price"]
            runtime.CONFIG.max_slippage = original["config_max_slippage"]


def run_paper_scan(max_price: Optional[float] = None, max_slippage: Optional[float] = None) -> Dict[str, object]:
    with isolated_scan_environment(max_price=max_price, max_slippage=max_slippage):
        runtime._cal = runtime.load_cal()
        output = io.StringIO()
        with redirect_stdout(output):
            scan_result = runtime.scan_and_update()
        markets = storage.load_all_markets()
        open_positions = []
        for market in markets:
            position = market.get("position")
            if not position or position.get("status") != "open":
                continue
            open_positions.append(
                {
                    "city": market["city_name"],
                    "date": market["date"],
                    "bucket": f"{position['bucket_low']}-{position['bucket_high']}{market['unit']}",
                    "entry_price": position["entry_price"],
                    "shares": position["shares"],
                    "cost": position["cost"],
                    "ev": position["ev"],
                    "probability": position["p"],
                    "source": position["forecast_src"],
                }
            )
        return {
            "filters": {
                "max_price": runtime.MAX_PRICE,
                "max_slippage": runtime.MAX_SLIPPAGE,
            },
            "log": [line for line in output.getvalue().splitlines() if line.strip()],
            "scan_result": {
                "new": scan_result[0],
                "closed": scan_result[1],
                "resolved": scan_result[2],
            },
            "positions": open_positions,
        }


def format_paper_scan_report(report: Dict[str, object]) -> str:
    return json.dumps(report, indent=2)
