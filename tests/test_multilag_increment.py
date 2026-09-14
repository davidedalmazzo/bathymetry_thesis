import numpy as np
import pytest
from umbra_sar.multilag_increment import (lag_pairs, increment_structure, primary_score,
    sinusoid_increment_energy, observed_constant_offset_identity, calibration_threshold, b_decision)


def test_constant_observed_offset_cancels_from_increments():
    z = np.array([1+1j, 2-3j, -1+2j])
    assert observed_constant_offset_identity(z, 4-2j) < 1e-14


def test_noiseless_complex_sinusoid_increment_formula():
    s, dt = .41, np.array([.7, 2.1, 5.0])
    z0 = np.exp(1j*s*np.r_[0., dt])
    got = abs(z0[1:] - z0[0])**2
    assert np.allclose(got, sinusoid_increment_energy(1, s, dt))


def test_irregular_times_are_classed_by_actual_lags():
    t = np.array([0., .7, 1.9, 4.2, 7.8])
    classes = lag_pairs(t, [0.6, 2.0, 5.0, 9.0], min_pairs=1)
    assert [len(c[0]) for c in classes] == [3, 4, 3]


def test_variable_transfer_makes_source_static_term_nonconstant_observed():
    t = np.array([0., 1., 2.])
    source_static = 2+1j
    h = np.array([1., 1.2, 1.4])
    assert np.max(abs(np.diff(h*source_static))) > 0


def test_near_zero_normalization_is_degenerate():
    out = increment_structure(np.zeros((4, 2), complex), [0, 1, 2, 3], [0.5, 2, 4], min_pairs=1)
    assert not out['valid'] and out['reason'] == 'near_zero_energy' and primary_score(out) is None


def test_support_weights_are_not_replicates_and_are_normalized():
    z = np.array([[0, 0], [1, 3], [0, 0], [1, 3]], complex)
    a = increment_structure(z, [0, 1, 2, 3], [.5, 1.5, 4], weights=[1, 3], min_pairs=1)
    b = increment_structure(z, [0, 1, 2, 3], [.5, 1.5, 4], weights=[2, 6], min_pairs=1)
    assert np.allclose(a['values'], b['values'])


def test_invalid_time_order_is_rejected():
    with pytest.raises(ValueError):
        lag_pairs([0, 1, 1], [0, 2])


def test_missing_lag_class_is_invalid_not_silently_dropped():
    out = increment_structure(np.ones((3, 1)), [0, 1, 2], [.5, 1.5, 100], min_pairs=3)
    assert not out['valid']


def test_threshold_is_frozen_from_calibration_not_evaluation_scores():
    threshold = calibration_threshold([.3, .4, .5, .6], .05)
    assert threshold == .4 and b_decision(.29, threshold) and not b_decision(.41, threshold)


def test_seed_split_is_declared_disjoint_in_frozen_config():
    import json
    from pathlib import Path
    cfg = json.loads((Path(__file__).parents[1] / 'Vandenberg/results/analysis_block15/BLOCK15J_CONFIG.json').read_text())
    seed = cfg['simulation']['seeds']
    assert seed['calibration'] != seed['evaluation']
