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
