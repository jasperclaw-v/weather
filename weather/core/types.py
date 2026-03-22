"""Typed domain objects used across modules."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Location:
    slug: str
    name: str
    station: str
    lat: float
    lon: float
    unit: str
    region: str


@dataclass
class ForecastSnapshot:
    ts: str
    horizon: str
    hours_left: float
    best: Optional[float]
    best_source: Optional[str]
    ecmwf: Optional[float] = None
    hrrr: Optional[float] = None
    metar: Optional[float] = None


@dataclass
class WeatherBucket:
    low: float
    high: float
    question: str = ""
    market_id: str = ""


@dataclass
class MarketQuote:
    question: str
    market_id: str
    low: float
    high: float
    bid: float
    ask: float
    spread: float
    volume: float


@dataclass
class Position:
    market_id: str
    bucket_low: float
    bucket_high: float
    entry_price: float
    shares: float
    cost: float
    forecast_src: str
    forecast_temp: float
    sigma: float
    status: str = "open"
    bid_at_entry: float = 0.0
    ev: float = 0.0
    kelly: float = 0.0
    pnl: Optional[float] = None
    stop_price: Optional[float] = None
    trailing_activated: bool = False
    opened_at: str = ""
    closed_at: Optional[str] = None
    close_reason: Optional[str] = None
    exit_price: Optional[float] = None


@dataclass
class MarketRecord:
    city: str
    city_name: str
    date: str
    unit: str
    station: str
    event_end_date: str
    hours_at_discovery: float
    status: str = "open"
    position: Optional[Dict] = None
    actual_temp: Optional[float] = None
    resolved_outcome: Optional[str] = None
    pnl: Optional[float] = None
    forecast_snapshots: List[Dict] = field(default_factory=list)
    market_snapshots: List[Dict] = field(default_factory=list)
    all_outcomes: List[Dict] = field(default_factory=list)
    created_at: str = ""


@dataclass
class CalibrationRecord:
    sigma: float
    n: int
    updated_at: str
    method: str = "residual_stddev"


@dataclass
class PortfolioState:
    balance: float
    starting_balance: float
    total_trades: int
    wins: int
    losses: int
    peak_balance: float


@dataclass
class RiskResult:
    action: str = "hold"
    reason: str = ""
    exit_price: float = 0.0
    pnl: float = 0.0
    trailing_activated: bool = False

