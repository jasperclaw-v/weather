from weather.backtests.engine import replay_markets
from weather.backtests.metrics import brier_score, max_drawdown, sharpe_ratio


def test_brier_score_is_computed():
    assert brier_score([0.8, 0.2], [1, 0]) == 0.04


def test_max_drawdown_uses_running_equity():
    assert max_drawdown([10.0, -20.0, 5.0]) == 20.0


def test_sharpe_ratio_handles_nonzero_series():
    assert sharpe_ratio([10.0, -5.0, 15.0]) != 0.0


def test_replay_markets_summarizes_trades():
    markets = [
        {
            "city": "nyc",
            "date": "2026-03-22",
            "resolved_outcome": "win",
            "pnl": 12.0,
            "position": {
                "market_id": "m1",
                "p": 0.65,
                "close_reason": "resolved",
            },
        },
        {
            "city": "chicago",
            "date": "2026-03-23",
            "resolved_outcome": "loss",
            "pnl": -8.0,
            "position": {
                "market_id": "m2",
                "p": 0.40,
                "close_reason": "resolved",
            },
        },
    ]
    summary = replay_markets(markets)
    assert summary["n_trades"] == 2
    assert summary["total_pnl"] == 4.0
    assert summary["win_rate"] == 0.5
    assert summary["brier"] == 0.14125
