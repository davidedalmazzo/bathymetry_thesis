import numpy as np
import pytest
import forward_lambda_check as fl


def test_dispersion_solution():
    om = 2 * np.pi / np.array([8.0, 12.0]); h = np.array([5.0, 20.0])
    k = fl.k_from_omega(om, h)
    assert np.allclose(om ** 2, 9.80665 * k * np.tanh(k * h))


def test_predicted_radial_conserves_variance():
    f = np.linspace(0.04, 0.3, 200); e = np.exp(-((f - 0.08) / 0.01) ** 2)
    kb = np.linspace(0, 1.0, 400)
    S = fl.predicted_radial(f, e, [8.0], kb, False)
    assert np.sum(S * np.diff(kb)) == pytest.approx(np.sum(e * np.gradient(f)), rel=1e-6)
    kc = 0.5 * (kb[1:] + kb[:-1]); kp, kcen, _ = fl.peak_and_centroid(kc, S)
    assert kp == pytest.approx(fl.k_from_omega(2 * np.pi * 0.08, 8.0), rel=0.06)   # Jacobian df/dk shifts the E(k) peak slightly


def test_block_bootstrap_ci_widens_with_correlated_windows():
    import forward_lambda_check as fc
    rng = np.random.default_rng(1)
    # 20 blocks x 50 near-identical windows: the effective sample is 20, not 1000
    block_mean = rng.normal(0.05, 0.10, 20)
    vals = np.concatenate([m + rng.normal(0, 1e-3, 50) for m in block_mean])
    blocks = np.repeat(np.arange(20), 50)
    r = fc.block_bootstrap(vals, blocks, 500, np.random.default_rng(0))
    assert r["n"] == 1000 and r["n_blocks"] == 20
    lo, hi = r["median_ci95_block_bootstrap"]
    assert lo < r["median"] < hi
    naive = 1.4826 * np.median(np.abs(vals - np.median(vals))) / np.sqrt(1000)
    assert (hi - lo) / 2 > 5 * naive          # naive per-window CI is far too narrow


def test_fixed_sector_ignores_spurious_maximum():
    import forward_lambda_check as fc
    k = np.linspace(-0.2, 0.2, 81); KE, KN = np.meshgrid(k, k)
    mask = np.hypot(KE, KN) > 1e-9
    P = np.full(KE.shape, 0.1)
    swell = np.exp(-(((KE - 0.0) ** 2 + (KN - 0.06) ** 2) / (2 * 0.008 ** 2)))   # along N, k=0.06
    spur = 3 * np.exp(-(((KE - 0.15) ** 2 + (KN - 0.0) ** 2) / (2 * 0.004 ** 2)))  # brighter noise lobe along E
    P = P + swell + spur
    _, _, th_sar, _, th_max = fc.sar_radial(P, mask, k, 30.0)
    _, S_fix, th_fix, _, _ = fc.sar_radial(P, mask, k, 30.0, th_fixed=0.0)
    assert abs(th_sar - 90) < 10 and abs(th_max - 90) < 10        # SAR-driven sector follows the noise lobe
    assert th_fix == 0.0
    kb = np.arange(0, np.hypot(KE, KN)[mask].max() + (k[1] - k[0]), k[1] - k[0])
    kc = 0.5 * (kb[1:] + kb[:-1])
    kp, _, _ = fc.peak_and_centroid(kc[: len(S_fix)], S_fix)
    assert abs(kp - 0.06) < 0.01
