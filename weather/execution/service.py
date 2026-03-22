"""Execution service that bridges strategy signals into the order router."""

from typing import Any, Dict, Optional

from weather.execution.auth import PolymarketAuthConfig
from weather.execution.router import PolymarketOrderRouter, order_intent_from_signal


class ExecutionService:
    def __init__(self, router: PolymarketOrderRouter):
        self.router = router

    @classmethod
    def from_auth_config(cls, auth: PolymarketAuthConfig) -> "ExecutionService":
        return cls(PolymarketOrderRouter(auth))

    def execute_signal(self, signal: dict) -> Dict[str, Any]:
        intent = order_intent_from_signal(signal)
        result = self.router.submit_order(intent)
        return {
            "intent": intent.__dict__,
            "result": result,
        }


def maybe_execute_signal(signal: dict, execution_service: Optional[ExecutionService]) -> Optional[Dict[str, Any]]:
    if execution_service is None:
        return None
    return execution_service.execute_signal(signal)
