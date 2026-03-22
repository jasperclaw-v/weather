import sys
import types

from weather.execution.auth import load_polymarket_auth_from_env
from weather.execution.router import OrderIntent, PolymarketOrderRouter


class FakeCreds:
    def __init__(self, api_key, api_secret, api_passphrase):
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase


class FakeOrderType:
    GTC = "GTC"
    GTD = "GTD"
    FOK = "FOK"


class FakeOrderArgs:
    def __init__(self, token_id, price, size, side):
        self.token_id = token_id
        self.price = price
        self.size = size
        self.side = side


class FakePostOrdersArgs:
    def __init__(self, order, orderType):
        self.order = order
        self.orderType = orderType


class FakeClobClient:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    def create_or_derive_api_creds(self):
        return FakeCreds("k", "s", "p")

    def create_order(self, args):
        return {"built": args.token_id, "price": args.price, "size": args.size, "side": args.side}

    def post_order(self, order, orderType=None):
        return {"posted": order, "orderType": orderType}

    def post_orders(self, args):
        return {"posted_count": len(args)}

    def cancel_all(self):
        return {"cancelled": True}

    def get_orders(self, params=None):
        return {"orders": []}

    def get_midpoint(self, token_id):
        return 0.51

    def get_spread(self, token_id):
        return 0.02

    def get_order_book(self, token_id):
        return {"asset_id": token_id}


def install_fake_clob_modules(monkeypatch):
    client_mod = types.SimpleNamespace(ClobClient=FakeClobClient)
    types_mod = types.SimpleNamespace(
        ApiCreds=FakeCreds,
        OrderType=FakeOrderType,
        OrderArgs=FakeOrderArgs,
        PostOrdersArgs=FakePostOrdersArgs,
    )
    monkeypatch.setitem(sys.modules, "py_clob_client.client", client_mod)
    monkeypatch.setitem(sys.modules, "py_clob_client.clob_types", types_mod)


def test_load_polymarket_auth_from_env(monkeypatch):
    monkeypatch.setenv("POLY_API_KEY", "key")
    monkeypatch.setenv("POLY_API_SECRET", "secret")
    monkeypatch.setenv("POLY_API_PASSPHRASE", "pass")
    cfg = load_polymarket_auth_from_env()
    assert cfg.api_key == "key"
    assert cfg.has_l2 is True


def test_router_submit_order_dry_run(monkeypatch):
    install_fake_clob_modules(monkeypatch)
    cfg = load_polymarket_auth_from_env()
    cfg.dry_run = True
    router = PolymarketOrderRouter(cfg)
    result = router.submit_order(OrderIntent(token_id="1", side="BUY", price=0.5, size=10))
    assert result["status"] == "dry_run"


def test_router_derive_creds_and_post(monkeypatch):
    install_fake_clob_modules(monkeypatch)
    monkeypatch.setenv("POLY_PRIVATE_KEY", "0xabc")
    monkeypatch.setenv("POLY_DRY_RUN", "false")
    cfg = load_polymarket_auth_from_env()
    router = PolymarketOrderRouter(cfg)
    creds = router.ensure_api_credentials()
    assert creds.api_key == "k"
    result = router.submit_order(OrderIntent(token_id="1", side="BUY", price=0.5, size=10))
    assert result["orderType"] == "GTC"


def test_router_estimate_fill(monkeypatch):
    install_fake_clob_modules(monkeypatch)
    cfg = load_polymarket_auth_from_env()
    router = PolymarketOrderRouter(cfg)
    estimate = router.estimate_fill("1", "BUY", 5)
    assert estimate["midpoint"] == 0.51
    assert estimate["spread"] == 0.02
