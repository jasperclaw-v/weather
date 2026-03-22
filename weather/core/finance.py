"""Expected value and Kelly sizing helpers."""

from .constants import DEFAULT_KELLY_FRACTION, DEFAULT_MAX_BET


def calc_ev(probability: float, price: float, fee: float = 0.0) -> float:
    """Expected value for buying YES, net of a simple fee estimate."""
    if price <= 0 or price >= 1:
        return 0.0
    return round(probability - price - fee, 4)


def calc_kelly(
    probability: float,
    price: float,
    fraction: float = DEFAULT_KELLY_FRACTION,
) -> float:
    """Fractional Kelly position fraction."""
    if price <= 0 or price >= 1:
        return 0.0
    b = 1.0 / price - 1.0
    q = 1.0 - probability
    raw = (probability * b - q) / b
    return round(min(max(0.0, raw) * fraction, 1.0), 4)


def bet_size(kelly_fraction: float, balance: float, max_bet: float = DEFAULT_MAX_BET) -> float:
    """Dollar position size."""
    return round(min(kelly_fraction * balance, max_bet), 2)

