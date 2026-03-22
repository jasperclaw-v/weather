"""Polymarket execution credential loading."""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class PolymarketApiCreds:
    api_key: str
    api_secret: str
    api_passphrase: str


@dataclass
class PolymarketAuthConfig:
    host: str = "https://clob.polymarket.com"
    chain_id: int = 137
    private_key: str = ""
    signature_type: int = 0
    funder: Optional[str] = None
    api_key: str = ""
    api_secret: str = ""
    api_passphrase: str = ""
    dry_run: bool = True

    @property
    def has_l1(self) -> bool:
        return bool(self.private_key)

    @property
    def has_l2(self) -> bool:
        return bool(self.api_key and self.api_secret and self.api_passphrase)

    def to_api_creds(self) -> Optional[PolymarketApiCreds]:
        if not self.has_l2:
            return None
        return PolymarketApiCreds(
            api_key=self.api_key,
            api_secret=self.api_secret,
            api_passphrase=self.api_passphrase,
        )


def load_polymarket_auth_from_env() -> PolymarketAuthConfig:
    return PolymarketAuthConfig(
        host=os.getenv("POLY_HOST", "https://clob.polymarket.com"),
        chain_id=int(os.getenv("POLY_CHAIN_ID", "137")),
        private_key=os.getenv("POLY_PRIVATE_KEY", ""),
        signature_type=int(os.getenv("POLY_SIGNATURE_TYPE", "0")),
        funder=os.getenv("POLY_FUNDER") or None,
        api_key=os.getenv("POLY_API_KEY", ""),
        api_secret=os.getenv("POLY_API_SECRET", ""),
        api_passphrase=os.getenv("POLY_API_PASSPHRASE", ""),
        dry_run=os.getenv("POLY_DRY_RUN", "true").lower() != "false",
    )
