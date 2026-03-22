"""Performance and calibration metrics for replayed trades."""

from math import sqrt
from statistics import mean, pstdev
from typing import Iterable, List, Optional


def brier_score(probabilities: Iterable[float], outcomes: Iterable[int]) -> float:
    probs = list(probabilities)
    outs = list(outcomes)
    if not probs or len(probs) != len(outs):
        return 0.0
    return round(mean((p - o) ** 2 for p, o in zip(probs, outs)), 6)


def max_drawdown(pnls: Iterable[float]) -> float:
    equity = 0.0
    peak = 0.0
    worst = 0.0
    for pnl in pnls:
        equity += pnl
        peak = max(peak, equity)
        worst = min(worst, equity - peak)
    return round(abs(worst), 2)


def sharpe_ratio(pnls: Iterable[float]) -> float:
    values = list(pnls)
    if len(values) < 2:
        return 0.0
    sigma = pstdev(values)
    if sigma == 0:
        return 0.0
    return round(mean(values) / sigma, 4)


def sortino_ratio(pnls: Iterable[float]) -> float:
    values = list(pnls)
    if len(values) < 2:
        return 0.0
    downside = [pnl for pnl in values if pnl < 0]
    if not downside:
        return 0.0
    downside_sigma = pstdev(downside)
    if downside_sigma == 0:
        return 0.0
    return round(mean(values) / downside_sigma, 4)


def win_rate(outcomes: Iterable[int]) -> float:
    values = list(outcomes)
    if not values:
        return 0.0
    return round(sum(values) / len(values), 4)

