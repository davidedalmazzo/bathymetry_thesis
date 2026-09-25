import numpy as np
from forward_lambda_check import footprint_depths


def test_random_mode_consumes_the_legacy_stream():
    d = np.linspace(5, 25, 500)
    small = d[:40]
    a, b = np.random.default_rng(0), np.random.default_rng(0)
    for x in (d, small, d):          # legacy expression: rng.choice(d, size=min(n, d.size), replace=False)
        np.testing.assert_array_equal(footprint_depths(x, "random", 60, a), b.choice(x, size=min(60, x.size), replace=False))


def test_quantile_and_all_are_deterministic():
    d = np.random.default_rng(1).uniform(5, 25, 1000)
    q = footprint_depths(d, "quantile", 60, None)
    assert q.size == 60 and np.all(np.diff(q) >= 0)
    np.testing.assert_allclose(q, np.quantile(d, (np.arange(60) + 0.5) / 60))
    np.testing.assert_array_equal(footprint_depths(d, "all", 60, None), d)
    np.testing.assert_array_equal(footprint_depths(d[:30], "quantile", 60, None), d[:30])
