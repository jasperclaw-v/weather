"""Runtime configuration loader."""

import json
from pathlib import Path
from typing import Any, Dict

CONFIG_PATH = Path("config.json")


def load_config() -> Dict[str, Any]:
    if CONFIG_PATH.exists():
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return {}
