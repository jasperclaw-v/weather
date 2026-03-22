"""Optional wrapper around the official Polymarket Python CLOB client."""

from dataclasses import dataclass
from importlib import import_module
from typing import Any, Dict, List, Optional

from weather.execution.auth import PolymarketApiCreds, PolymarketAuthConfig


class MissingPolymarketClientError(RuntimeError):
    pass


def _load_clob_modules():
    try:
        client_mod = import_module("py_clob_client.client")
        types_mod = import_module("py_clob_client.clob_types")
    except Exception as exc:  # pragma: no cover
        raise MissingPolymarketClientError(
            "Official Polymarket client missing. Install from "
            "https://github.com/Polymarket/py-clob-client"
        ) from exc
    return client_mod, types_mod


@dataclass
class OrderIntent:
    token_id: str
    side: str
    price: float
    size: float
    order_type: str = "GTC"


class PolymarketOrderRouter:
    def __init__(self, auth: PolymarketAuthConfig):
        self.auth = auth
        self._client = None
        self._types = None

    def connect(self):
        client_mod, types_mod = _load_clob_modules()
        creds = None
        if self.auth.has_l2:
            creds = types_mod.ApiCreds(
                api_key=self.auth.api_key,
                api_secret=self.auth.api_secret,
                api_passphrase=self.auth.api_passphrase,
            )
        self._client = client_mod.ClobClient(
            self.auth.host,
            chain_id=self.auth.chain_id,
            key=self.auth.private_key or None,
            creds=creds,
            signature_type=self.auth.signature_type,
            funder=self.auth.funder,
        )
        self._types = types_mod
        return self._client

    @property
    def client(self):
        return self._client or self.connect()

    def ensure_api_credentials(self) -> Optional[PolymarketApiCreds]:
        if self.auth.has_l2:
            return self.auth.to_api_creds()
        if not self.auth.has_l1:
            return None
        creds = self.client.create_or_derive_api_creds()
        if creds is None:
            return None
        self.auth.api_key = creds.api_key
        self.auth.api_secret = creds.api_secret
        self.auth.api_passphrase = creds.api_passphrase
        return PolymarketApiCreds(
            api_key=creds.api_key,
            api_secret=creds.api_secret,
            api_passphrase=creds.api_passphrase,
        )

    def build_order(self, intent: OrderIntent):
        side = getattr(self._types, "BUY" if intent.side.upper() == "BUY" else "SELL", None)
        if side is None:
            side = intent.side.upper()
        args = self._types.OrderArgs(
            token_id=intent.token_id,
            price=float(intent.price),
            size=float(intent.size),
            side=side,
        )
        return self.client.create_order(args)

    def submit_order(self, intent: OrderIntent) -> Dict[str, Any]:
        if self.auth.dry_run:
            return {
                "status": "dry_run",
                "token_id": intent.token_id,
                "side": intent.side,
                "price": intent.price,
                "size": intent.size,
                "order_type": intent.order_type,
            }

        order = self.build_order(intent)
        order_type = getattr(self._types.OrderType, intent.order_type)
        return self.client.post_order(order, orderType=order_type)

    def submit_orders(self, intents: List[OrderIntent]) -> Dict[str, Any]:
        if self.auth.dry_run:
            return {"status": "dry_run", "orders": [intent.__dict__ for intent in intents]}
        args = []
        for intent in intents:
            order = self.build_order(intent)
            order_type = getattr(self._types.OrderType, intent.order_type)
            args.append(self._types.PostOrdersArgs(order=order, orderType=order_type))
        return self.client.post_orders(args)

    def cancel_all(self):
        if self.auth.dry_run:
            return {"status": "dry_run", "action": "cancel_all"}
        return self.client.cancel_all()

    def get_open_orders(self, params=None):
        return self.client.get_orders(params=params)

    def estimate_fill(self, token_id: str, side: str, size: float) -> Dict[str, Any]:
        midpoint = self.client.get_midpoint(token_id)
        spread = self.client.get_spread(token_id)
        orderbook = self.client.get_order_book(token_id)
        return {
            "token_id": token_id,
            "side": side,
            "size": size,
            "midpoint": midpoint,
            "spread": spread,
            "orderbook": orderbook,
        }
