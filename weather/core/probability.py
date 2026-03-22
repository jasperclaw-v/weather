"""Gaussian bucket probability for all weather market bucket types."""

import math
from typing import Optional

from .constants import DEFAULT_SIGMA_F, NEG_INF_BUCKET, POS_INF_BUCKET

try:
    from scipy.stats import norm
except Exception:  # pragma: no cover
    norm = None


def normal_cdf(x: float, loc: float = 0.0, scale: float = 1.0) -> float:
    """Evaluate the normal CDF with a scipy fallback."""
    if scale <= 0:
        raise ValueError("scale must be positive")
    if norm is not None:
        return float(norm.cdf(x, loc=loc, scale=scale))
    z = (x - loc) / (scale * math.sqrt(2.0))
    return 0.5 * (1.0 + math.erf(z))


def bucket_probability(
    forecast: float,
    t_low: float,
    t_high: float,
    sigma: Optional[float] = None,
) -> float:
    """Return the probability the realized temperature lands in the bucket."""
    scale = sigma if sigma is not None and sigma > 0 else DEFAULT_SIGMA_F

    if t_low == t_high and t_low > NEG_INF_BUCKET:
        lo = normal_cdf(t_low - 0.5, loc=forecast, scale=scale)
        hi = normal_cdf(t_high + 0.5, loc=forecast, scale=scale)
        return round(max(0.0, hi - lo), 6)

    lo = 0.0 if t_low <= NEG_INF_BUCKET else normal_cdf(t_low, loc=forecast, scale=scale)
    hi = 1.0 if t_high >= POS_INF_BUCKET else normal_cdf(t_high, loc=forecast, scale=scale)
    return round(max(0.0, hi - lo), 6)


def in_bucket(forecast: float, t_low: float, t_high: float) -> bool:
    """Compatibility helper retained for non-probabilistic checks."""
    if t_low == t_high:
        return round(float(forecast)) == round(t_low)
    return t_low <= float(forecast) <= t_high

