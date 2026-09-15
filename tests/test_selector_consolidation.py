import json
from pathlib import Path

import numpy as np

from umbra_sar.selector_consolidation import (
    cdip_reference_admissible, depth_variance, dispersion_derivatives, dispersion_omega, estimate_tone_frequency,
    integrate_density, joint_directional_validity, roi_proxy_semantics,
    ndbc_archive_plan, select_reference, synthesize_band, temporal_budgets,
)


def test_missing_bins_not_bridged_and_explicit_widths():
    out = integrate_density([.05, .06, .08], [1, np.nan, 1], widths_hz=[.01, .01, .02])
    assert np.isclose(out["energy"], .03)
    assert out["valid_bin_count"] == 2


def test_joint_completeness_is_not_any_finite():
    f = [.05, .06, .07]; e = [1, 8, 1]
    out = joint_directional_validity(f, e, [1, np.nan, 1], [1, 1, 1],
                                     [.8, .8, .8], [.7, .7, .7], widths_hz=[1, 1, 1])
    assert not out["admissible"] and np.isclose(out["energy_coverage"], .2)


def test_reference_skips_nearest_bad_and_out_of_time():
    attempts = [
        {"station_id": "A", "distance_km": 5, "outcome": "network_error"},
        {"station_id": "B", "distance_km": 10, "outcome": "recovered", "offset_s": 5000, "joint_energy_coverage": 1},
        {"station_id": "C", "distance_km": 12, "outcome": "recovered", "offset_s": 40, "joint_energy_coverage": .95},
    ]
    assert select_reference(attempts)["selected"]["station_id"] == "C"


def test_out_of_time_reference_does_not_override_model_and_network_is_not_absence():
    model={"period_s": 12, "role": "screening_only"}
    out=select_reference([{"station_id":"A","distance_km":2,"outcome":"recovered","offset_s":5000,"joint_energy_coverage":1},
                          {"station_id":"B","distance_km":3,"outcome":"network_error"}], model=model)
    assert out["selected"] is None and out["screening_fallback"] == model
    assert [a["decision"] for a in out["attempts"]] == ["temporal_mismatch","network_error"]


def test_archive_plan_is_dynamic_and_cdip_requires_verified_deployment():
    p=ndbc_archive_plan("42084",2025)
    assert "9999" in p["candidates"][0] and "2025" in p["candidates"][1]
    assert "98" not in str(p)
    assert not cdip_reference_admissible(True,False,True)
    assert cdip_reference_admissible(True,True,True)


def test_temporal_paths_and_roi_names_are_honest():
    b = temporal_budgets(22.54, 18.068, 6)
    assert b["cphd_phase_history"]["nominal_nonoverlapping_aperture_count"] == 3
    assert b["sicd_processed_image"]["duration_s"] == 18.068
    assert not b["cphd_phase_history"]["statistical_independence_demonstrated"]
    assert not roi_proxy_semantics(100)["is_maximum_ocean_roi_diameter"]


def test_corrected_width_and_legacy_narrowing_on_archived_irregular_times():
    p = Path("Vandenberg/results/analysis_block12/BLOCK12_PHASE_SLOPE.json")
    times = np.asarray(json.loads(p.read_text())["look_times_s"])
    corr=[]; old=[]
    for seed in range(40):
        corr.append(synthesize_band(times, .08377, .177, 4000, np.random.default_rng(seed))["realized_energy_std_hz"])
        old.append(synthesize_band(times, .08377, .177, 4000, np.random.default_rng(seed), legacy=True)["realized_energy_std_hz"])
    target=.08377*.177
    assert abs(np.mean(corr)/target-1) < .03
    assert abs(np.mean(old)/target-1/np.sqrt(2)) < .04


def test_epsilon_zero_reproducible_and_nonphysical_frequency_rejected():
    t=[0,.7,1.5]
    a=synthesize_band(t,.08,0,20,np.random.default_rng(8))
    b=synthesize_band(t,.08,0,20,np.random.default_rng(8))
    assert np.array_equal(a["signal"],b["signal"])
    broad=synthesize_band(t,.02,2,1000,np.random.default_rng(9))
    assert np.all(broad["frequencies_hz"] > 0)


def test_frozen_vandenberg_invariants_are_unchanged():
    b12=json.loads(Path("Vandenberg/results/analysis_block12/BLOCK12_PHASE_SLOPE.json").read_text())
    b15=json.loads(Path("Vandenberg/results/analysis_block15/BLOCK15K_SUMMARY.json").read_text())
    assert len(b12["look_times_s"]) == 32
    assert b15  # read-only guard: frozen artifact remains parseable and present


def test_off_grid_tone_precision_better_than_fourier_spacing():
    t=np.array([0., .71, 1.42, 2.1, 3.05, 4.2, 5.6, 7.1, 8.9, 11.])
    f=.083731
    z=np.exp(2j*np.pi*f*t)
    est=estimate_tone_frequency(t,z,(.06,.11))
    assert abs(est-f) < 1e-5
    assert abs(est-f) < 1/(t.max()-t.min())


def test_dispersion_derivatives_covariance_and_finite_band_consistency():
    k=.06; h=12
    d=dispersion_derivatives(k,h)
    eps=1e-6
    numeric=(dispersion_omega(k+eps,h)-dispersion_omega(k-eps,h))/(2*eps)
    assert np.isclose(d["group_velocity"], numeric, rtol=1e-6)
    a=depth_variance(k,h,1e-6,1e-5,0)
    b=depth_variance(k,h,1e-6,1e-5,8e-7)
    assert a["variance_h"] != b["variance_h"]
    for kk in [.045,.06,.08]:
        om=dispersion_omega(kk,h)
        # direct residual at the same depth: finite-band points share one h
        assert abs(om**2-9.80665*kk*np.tanh(kk*h)) < 1e-12
