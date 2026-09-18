"""Estimator-level tests only; no radar formation or source data reads."""
import json
from pathlib import Path

import numpy as np
import pytest

from umbra_sar.frequency_comparison import (
    local_msc, reference_fit, estimate_circular, pair_observations,
)

ROOT = Path(__file__).resolve().parents[1]


def times(real):
    if not real:
        return np.arange(32)*0.7
    manifest = ROOT/'umbra/Vandenberg/results/block12_backprojection/BLOCK12_SUBLOOK_MANIFEST.json'
    return np.array(json.loads(manifest.read_text())['mean_tx_time_per_look_s'])


@pytest.mark.parametrize('real', [False, True])
@pytest.mark.parametrize('slope', [-0.63, 0.63])
def test_isolated_component_actual_and_regular_times(real, slope):
    t = times(real)
    z = (1+0.1*np.sin(t))*np.exp(1j*(slope*t+2.7))
    bounds = (-0.8*np.pi/max(np.diff(t)), 0.8*np.pi/max(np.diff(t)))
    a = reference_fit(z, t, 16)
    assert abs(a['s_phi']-slope) < 1e-12
    for lags in [(1,), (1, 2, 4, 8)]:
        b = estimate_circular(z, t, lags, bounds)
        # Bounded scalar optimizer tolerance, not an ocean uncertainty.
        assert abs(b['s_phi']-slope) < 1e-6
        assert b['valid'] and b['circular_rms'] < 1e-6


def test_conjugation_and_cross_order_sign():
    t = times(True); z = np.exp(-0.51j*t)
    p, dt, w, labels = pair_observations(z, t)
    q, _, _, _ = pair_observations(z.conj(), t)
    reversed_order = np.angle(z[:-1]*z[1:].conj())
    np.testing.assert_allclose(q, -p, atol=1e-14)
    np.testing.assert_allclose(reversed_order, -p, atol=1e-14)
    assert reference_fit(z.conj(), t, 16)['s_phi'] == pytest.approx(0.51)


def test_wrapping_initial_phase_reference_and_telescoping():
    t = times(True); z = np.exp(1j*(-0.72*t+2.9))
    for ref in (0, 16, 31):
        for phase0 in (0, 2.3):
            a = reference_fit(z*np.exp(1j*phase0), t, ref)
            assert a['s_phi'] == pytest.approx(-0.72, abs=1e-12)
            assert a['unwrap_continuity_valid']
            assert max(abs(np.array(a['unwrap_turn_corrections']))) > 0
            assert abs(a['telescoping_error']) < 1e-12


def test_local_msc_coherent_zero_nonfinite_and_borders():
    rng = np.random.default_rng(1501)
    a = rng.normal(size=(17, 17))+1j*rng.normal(size=(17, 17))
    c, valid = local_msc(a, 2*a*np.exp(0.4j))
    np.testing.assert_allclose(c[1:-1, 1:-1], 1, atol=1e-12)
    assert not valid[0].any() and not valid[:, -1].any()
    c, valid = local_msc(a, np.zeros_like(a))
    assert not c.any() and not valid.any()
    a[8, 8] = np.nan
    c, valid = local_msc(a, a)
    assert not valid[7:10, 7:10].any() and np.isfinite(c).all()


def test_local_msc_decorrelated_is_not_one_and_matches_definition():
    rng = np.random.default_rng(1502)
    a = rng.normal(size=(101, 101))+1j*rng.normal(size=(101, 101))
    b = rng.normal(size=a.shape)+1j*rng.normal(size=a.shape)
    c, valid = local_msc(a, b)
    # Nine independent complex samples: expected MSC ~1/9. Broad interval
    # accommodates overlapping patches; this is not a CI over those patches.
    assert 0.08 < c[valid].mean() < 0.15
    p, q = a[49:52, 49:52], b[49:52, 49:52]
    expected = abs(np.mean(q*p.conj()))**2/(np.mean(abs(p)**2)*np.mean(abs(q)**2))
    assert c[50, 50] == pytest.approx(expected)
    assert np.allclose(abs(a*b.conj())/np.sqrt(abs(a)**2*abs(b)**2), 1)
    assert 0.3**2 == pytest.approx(0.09)


def test_lag_classes_equal_weight_and_aliases_reported():
    t = times(False); z = np.exp(-0.6j*t)
    _, _, w, labels = pair_observations(z, t, (1, 2, 4, 8))
    for lag in (1, 2, 4, 8):
        assert w[labels == lag].sum() == pytest.approx(0.25)
    fit = estimate_circular(z, t, (8,), (-3, 3))
    assert len(fit['minima']) > 1 and fit['ambiguous'] and not fit['valid']


def test_mixture_is_diagnostic_not_forced_to_mobile_truth():
    t = times(True); z = np.exp(-0.61j*t)+1.4
    a = reference_fit(z, t, 16)
    b = estimate_circular(z, t, (1,), (-3, 3))
    c = estimate_circular(z, t, (1, 2, 4, 8), (-3, 3))
    assert all(np.isfinite(f['s_phi']) for f in (a, b, c))
    assert abs(a['s_phi']+0.61) > 0.1


def test_invalid_time_zero_phase_and_large_steps_rejected():
    with pytest.raises(ValueError): reference_fit(np.ones(4), [0, 1, 1, 2], 0)
    with pytest.raises(ValueError): reference_fit(np.zeros(4), np.arange(4), 0)
    fit = reference_fit(np.exp(2.9j*np.arange(8)), np.arange(8), 0)
    assert not fit['unwrap_continuity_valid']


def test_circular_initial_phase_and_search_grid_refinement():
    t = times(True); z = np.exp(1j*(0.67*t+2.8))
    for lags in ((1,), (1, 2, 4, 8)):
        baseline = estimate_circular(z, t, lags, (-3, 3))
        shifted = estimate_circular(z*np.exp(2.2j), t, lags, (-3, 3), grid_size=4001)
        assert shifted['s_phi'] == pytest.approx(baseline['s_phi'], abs=1e-6)
        assert shifted['valid'] and baseline['valid']
