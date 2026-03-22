from weather.core.finance import bet_size, calc_ev, calc_kelly


def test_ev_is_probability_minus_price():
    assert calc_ev(0.38, 0.08) == 0.3


def test_kelly_is_fractional_and_clamped():
    assert calc_kelly(0.38, 0.08) == 0.0815


def test_bet_size_honors_max_bet():
    assert bet_size(0.5, 1000.0, max_bet=20.0) == 20.0
