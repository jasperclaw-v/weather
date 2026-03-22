from weather.execution.auth import PolymarketAuthConfig
from weather.execution.router import OrderIntent
from weather.execution.service import ExecutionService, maybe_execute_signal


class FakeRouter:
    def __init__(self):
        self.intents = []

    def submit_order(self, intent):
        self.intents.append(intent)
        return {"status": "dry_run", "token_id": intent.token_id}


def test_execution_service_converts_signal_to_intent():
    service = ExecutionService(FakeRouter())
    result = service.execute_signal(
        {
            "market_id": "123",
            "entry_price": 0.42,
            "shares": 10,
        }
    )
    assert result["intent"]["token_id"] == "123"
    assert result["result"]["status"] == "dry_run"


def test_maybe_execute_signal_returns_none_without_service():
    assert maybe_execute_signal({"market_id": "1", "entry_price": 0.4, "shares": 1}, None) is None
