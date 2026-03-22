from weather.core.probability import bucket_probability


def test_regular_bucket_is_probabilistic_not_binary():
    probability = bucket_probability(76.0, 75.0, 77.0, sigma=2.0)
    assert 0.38 < probability < 0.39


def test_edge_bucket_probability_is_bounded():
    probability = bucket_probability(76.0, -999.0, 75.0, sigma=2.0)
    assert 0.30 < probability < 0.31


def test_exact_bucket_uses_half_degree_window():
    probability = bucket_probability(76.0, 76.0, 76.0, sigma=2.0)
    assert 0.19 < probability < 0.20

