"""Block40: provenance resolution, window classification, pairing, spatial variance
reduction and frozen-artifact preservation."""
from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pytest

import block40_source_audit as audit
import block40_windows as bw
import block40_matched as bm
import block40_variance_ladder as bl
import s1_paper_peak as pp

ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- provenance
H12859 = {"source_survey_id": "H12859_MB_2m_MLLW_2of2", "source_institution": "DOC/NOAA/NOS/OCS",
          "survey_date_start": "2016-02-23", "survey_date_end": "2016-03-23",
          "coverage": "1", "bathy_coverage": "1", "vertical_uncert_fixed": "0.5"}
NGS1902 = {"source_survey_id": "NC1902-TB-C_BLK-06_US4NC1IK_ellipsoidal_dem",
           "source_institution": "DOC/NOAA/NOS/NGS/RSD", "survey_date_start": "2019-11-26",
           "survey_date_end": "2020-06-22", "coverage": "1", "bathy_coverage": "1"}
USACE2019 = {"source_survey_id": "2019_USACE_topobathyDEM_NC_Job1138067", "survey_date_start": "2019-06-18",
             "survey_date_end": "2019-06-25", "coverage": "1", "bathy_coverage": "1"}
INTERP1970 = {"source_survey_id": "H09171.interpolated", "survey_date_start": "1970-01-01",
              "survey_date_end": "1970-01-01", "coverage": "0", "bathy_coverage": "0"}
GENERALIZED = {"source_survey_id": "NBS Generalization", "survey_date_start": "1807-02-10",
               "survey_date_end": "1807-02-10", "coverage": "0", "bathy_coverage": "0"}


def test_direct_flag_uses_coverage_and_survey_id():
    assert audit.is_direct(H12859) and audit.is_direct(USACE2019) and audit.is_direct(NGS1902)
    assert not audit.is_direct(INTERP1970)
    assert not audit.is_direct(GENERALIZED)
    # a survey id marked interpolated is never direct even if the flags claim coverage
    assert not audit.is_direct({**INTERP1970, "coverage": "1", "bathy_coverage": "1"})


def test_survey_age_at_acquisition():
    assert audit.survey_age_days(H12859) == pytest.approx(2046.0, abs=1.0)      # 2016-03-23 -> 2021-10-28
    assert audit.survey_age_days(USACE2019) == pytest.approx(856.0, abs=1.5)
    assert audit.survey_age_days(NGS1902) == pytest.approx(493.0, abs=1.5)


def test_h12859_is_recognised_and_pre2010_excluded():
    assert "h12859" in H12859["source_survey_id"].lower()
    for meta in (INTERP1970, GENERALIZED):
        assert not audit.is_direct(meta)
        assert int(meta["survey_date_start"][:4]) < 2010


def test_inventory_classes_from_the_real_run():
    """The committed inventory must keep NGS 2019-20 out of the certified class and
    H12859 in its own direct class."""
    import csv
    f = ROOT / "duck_frf/Block40_stratified_validation/BLOCK40_SOURCE_INVENTORY.csv"
    if not f.exists():
        pytest.skip("Block40 inventory not generated in this checkout")
    rows = {r["source_key"]: r for r in csv.DictReader(open(f))}
    assert rows["bluetopo_74726"]["class_name"] == "bluetopo_direct_2019_2020_uncertain"
    assert float(rows["bluetopo_74726"]["empirical_nmad_vs_frf_m"]) > 0.5
    assert rows["bluetopo_74730"]["class_name"] == "bluetopo_direct_2019_2020_certified"
    assert float(rows["bluetopo_74730"]["empirical_nmad_vs_frf_m"]) <= 0.5
    assert rows["bluetopo_76675"]["class_name"] == "bluetopo_direct_h12859_2016"
    assert rows["bluetopo_74161"]["class_name"] == "bluetopo_interpolated_or_pre2010"


# ------------------------------------------------------- window classification
def test_window_class_threshold_is_exact_at_90_percent():
    # band C admits class 4 (H12859)
    assert bw.window_class({4: 0.90, 7: 0.10}, 3, 0.90)[0] == "primary_admissible"
    assert bw.window_class({4: 0.8999, 7: 0.1001}, 3, 0.90)[0] != "primary_admissible"
    # the same footprint is admissible at the 0.75 sensitivity
    assert bw.window_class({4: 0.8999, 7: 0.1001}, 3, 0.75)[0] == "primary_admissible"


def test_window_class_mixed_and_non_primary_labels():
    assert bw.window_class({4: 0.5, 7: 0.5}, 3, 0.90)[0] == "mixed_source"
    assert bw.window_class({3: 0.95, 7: 0.05}, 2, 0.90)[0] == "direct_but_uncertain"
    assert bw.window_class({6: 0.99}, 3, 0.90)[0] == "interpolated"
    assert bw.window_class({7: 0.99}, 2, 0.90)[0] == "legacy_calibrated"
    # direct but the wrong epoch for the band: H12859 2016 cannot certify band B
    assert bw.window_class({4: 0.99}, 2, 0.90)[0] == "temporally_inadmissible"
    # FRF 2021 is the only class admitted in band A
    assert bw.window_class({1: 0.95}, 1, 0.90)[0] == "primary_admissible"
    assert bw.window_class({2: 0.95}, 1, 0.90)[0] == "temporally_inadmissible"


def test_source_fraction_in_footprint(tmp_path):
    """Footprint fractions come from the rasterised polygon, not from the window centre."""
    import rasterio
    from rasterio.transform import from_origin
    from rasterio.features import geometry_mask
    cls = np.zeros((40, 40), "float32"); cls[:, 20:] = 4.0; cls[:, :20] = 7.0
    path = tmp_path / "m.tif"
    T = from_origin(0, 400, 10, 10)
    with rasterio.open(path, "w", driver="GTiff", height=40, width=40, count=1, dtype="float32", transform=T,
                       crs="EPSG:32618") as ds:
        ds.write(cls, 1)
    with rasterio.open(path) as ds:
        poly = {"type": "Polygon", "coordinates": [[(200, 100), (400, 100), (400, 300), (200, 300), (200, 100)]]}
        inside = ~geometry_mask([poly], out_shape=(40, 40), transform=ds.transform, all_touched=True)
        sub = ds.read(1)[inside]
    frac = {int(k): float((sub == k).sum()) / sub.size for k in np.unique(sub)}
    assert frac[4] > 0.95 and frac.get(7, 0.0) < 0.05


# ----------------------------------------------------------------- pairing
def test_pairing_requires_geographic_identity_band_and_class():
    s = [{"E": 0.0, "N": 0.0, "band": 3, "window_class": "primary_admissible"},
         {"E": 500.0, "N": 0.0, "band": 3, "window_class": "primary_admissible"},
         {"E": 1000.0, "N": 0.0, "band": 3, "window_class": "primary_admissible"}]
    g = [{"E": 10.0, "N": 5.0, "band": 3, "window_class": "primary_admissible"},     # pairs with the first
         {"E": 505.0, "N": 0.0, "band": 2, "window_class": "primary_admissible"},    # wrong band
         {"E": 1100.0, "N": 0.0, "band": 3, "window_class": "primary_admissible"}]   # too far
    out = bm.pair_windows(s, g, 25.0)
    assert len(out) == 1
    r, q, off = out[0]
    assert r["E"] == 0.0 and q["E"] == 10.0 and off == pytest.approx(math.hypot(10, 5))
    # each GRD window is used at most once
    s2 = s[:1] + [{"E": 2.0, "N": 2.0, "band": 3, "window_class": "primary_admissible"}]
    assert len(bm.pair_windows(s2, g[:1], 25.0)) == 1


# ------------------------------------------- spatial variance reduction ladder
def synthetic_window(nl=64, ns=256, lam=150.0, bearing_deg=0.0, speckle=True, seed=0):
    """Intensity window with a sinusoidal modulation and multiplicative speckle,
    on a rectangular affine map (range 2.3 m, azimuth 14 m)."""
    rng = np.random.default_rng(seed)
    J = np.array([[2.3, 0.0], [0.0, 14.0]])
    L, S = np.mgrid[0:nl, 0:ns].astype(float)
    E = J[0, 0] * (S - S.mean()); N = J[1, 1] * (L - L.mean())
    k = 2 * np.pi / lam; th = math.radians(bearing_deg)
    field = 1.0 + 0.35 * np.sin(k * (E * math.sin(th) + N * math.cos(th)))
    if speckle:
        field = field * rng.exponential(1.0, field.shape)     # single-look intensity speckle
    return field.astype(float), S, L, J


def test_multilook_normalisation_and_lobe_conservation():
    sig, S, L, J = synthetic_window()
    k, _ = pp.k_grid(1024.0, 1, 0.3)
    peaks = {}
    for v in ("slc_single_look", "slc_incoherent_N2", "slc_incoherent_N4", "slc_multitaper_K4"):
        P, looks = bl.variant_spectra(sig, S, L, J, k, v)
        assert np.all(np.isfinite(P)) and P.max() > 0
        # taper-energy normalisation keeps the spectra on a comparable scale
        assert 1e-4 < np.median(P[P > 0]) / np.median(P[P > 0]) <= 1.0
        mask = np.ones((k.size, k.size), bool)
        KE, KN = np.meshgrid(k, k)
        mask &= np.hypot(KE, KN) > 4 * np.pi / 1024.0
        res = pp.paper_peak(np.sqrt(P), k, k, mask, n_levels=20, scale="log10", blob_method="contour")
        assert "wavelength_m" in res
        peaks[v] = (res["wavelength_m"], math.degrees(math.atan2(res["kx"], res["ky"])) % 180, looks)
    lam0 = peaks["slc_single_look"][0]
    for v, (lam, brg, looks) in peaks.items():
        assert abs(lam / lam0 - 1) < 0.25, (v, lam, lam0)          # the physical lobe is conserved
        assert min(abs(brg - 0), abs(brg - 180)) < 20, (v, brg)    # and stays along the wave direction
    assert peaks["slc_incoherent_N2"][2] == 2 and peaks["slc_incoherent_N4"][2] == 4
    assert peaks["slc_multitaper_K4"][2] == 4


def test_variance_reduction_does_not_sharpen_the_lobe():
    """Averaging must reduce the scatter of the estimate, never narrow the main lobe:
    a narrower lobe would be a false resolution gain."""
    sig, S, L, J = synthetic_window(seed=3)
    k, _ = pp.k_grid(1024.0, 1, 0.3)
    KE, KN = np.meshgrid(k, k)
    mask = np.hypot(KE, KN) > 4 * np.pi / 1024.0
    widths = {}; cv = {}
    for v in ("slc_single_look", "slc_incoherent_N2", "slc_incoherent_N4", "slc_multitaper_K4"):
        P, _ = bl.variant_spectra(sig, S, L, J, k, v)
        d = bl.diagnostics(P, k, mask, 4 * np.pi / 1024.0)
        widths[v] = d["lobe_halfpower_width_rad_m"]
        kr = np.hypot(KE, KN)
        ann = mask & (kr > 0.08)                                   # signal-free high-k annulus
        v_ = P[ann]; cv[v] = float(np.std(v_) / np.mean(v_))
    assert widths["slc_incoherent_N4"] >= widths["slc_single_look"] * 0.95
    assert widths["slc_multitaper_K4"] >= widths["slc_single_look"] * 0.95
    assert cv["slc_incoherent_N4"] < cv["slc_single_look"]
    assert cv["slc_multitaper_K4"] < cv["slc_single_look"]


def test_overlapping_looks_are_not_independent():
    """Two 50 %-overlapping sub-blocks give correlated periodograms, so their average
    cannot be treated as two independent looks."""
    sig, S, L, J = synthetic_window(seed=5)
    k, _ = pp.k_grid(1024.0, 1, 0.3)
    nl = sig.shape[0]
    a = sig[: nl // 2]; b = sig[nl // 4: nl // 4 + nl // 2]; c = sig[nl // 2:]
    def per(block):
        Sb = S[: block.shape[0]]; Lb = L[: block.shape[0]]
        P, _ = bl.variant_spectra(block, Sb, Lb, J, k, "slc_single_look")
        return P.ravel()
    Pa, Pb, Pc = per(a), per(b), per(c)
    r_overlap = np.corrcoef(Pa, Pb)[0, 1]
    r_disjoint = np.corrcoef(Pa, Pc)[0, 1]
    assert r_overlap > r_disjoint


def test_multitaper_is_reproducible():
    sig, S, L, J = synthetic_window(seed=7)
    k, _ = pp.k_grid(1024.0, 1, 0.3)
    P1, _ = bl.variant_spectra(sig, S, L, J, k, "slc_multitaper_K4")
    P2, _ = bl.variant_spectra(sig, S, L, J, k, "slc_multitaper_K4")
    assert np.allclose(P1, P2)
    assert np.allclose(bl.dpss_tapers(64, 2.5, 2), bl.dpss_tapers(64, 2.5, 2))


def test_conjugate_lobe_and_direction_sign():
    """The spectrum of a real field is Hermitian: the peak is defined up to k -> -k, and
    the reported bearing is axial (mod 180 deg)."""
    for brg in (30.0, 210.0):
        sig, S, L, J = synthetic_window(bearing_deg=brg, speckle=False)
        k, _ = pp.k_grid(1024.0, 1, 0.3)
        KE, KN = np.meshgrid(k, k)
        mask = np.hypot(KE, KN) > 4 * np.pi / 1024.0
        P, _ = bl.variant_spectra(sig, S, L, J, k, "slc_single_look")
        res = pp.paper_peak(np.sqrt(P), k, k, mask, n_levels=20, scale="log10", blob_method="contour")
        axial = math.degrees(math.atan2(res["kx"], res["ky"])) % 180
        assert min(abs(axial - 30.0), abs(axial - 210.0 % 180)) < 15


def test_kmin_cut_and_edge_flag():
    sig, S, L, J = synthetic_window(lam=400.0, speckle=False)
    k, _ = pp.k_grid(1024.0, 1, 0.3)
    KE, KN = np.meshgrid(k, k)
    mask = np.hypot(KE, KN) > 2 * np.pi / 1024.0
    P, _ = bl.variant_spectra(sig, S, L, J, k, "slc_single_look")
    loose = bl.diagnostics(P, k, mask, 2 * np.pi / 1024.0)       # lambda <= 1024 m allowed
    strict = bl.diagnostics(P, k, mask, 2 * np.pi / 300.0)       # lambda <= 300 m allowed
    assert loose["wavelength_m"] == pytest.approx(400.0, rel=0.2)
    assert strict["wavelength_m"] < 320.0                         # the 400 m lobe is cut out
    assert strict["peak_at_kmin_edge"] is True


# ------------------------------------------------------------- eta scenarios
def test_water_level_scenarios_shift_the_prediction_the_right_way():
    import block40_sensitivity as bs
    gt = ROOT / "outputs/ground_truth_s1a_20211028_ext20/wave_spectra.json"
    if not gt.exists():
        pytest.skip("wave spectra not available")
    sp = json.loads(gt.read_text())["FRF:waverider-17m"]
    f = np.asarray(sp["frequency_hz"], float); e = np.asarray(sp["energy_m2_hz"], float)
    l0 = bs.lambda_pred_spectrum(f, e, 20.0)
    lp = bs.lambda_pred_spectrum(f, e, 20.0 + 0.235)
    lm = bs.lambda_pred_spectrum(f, e, 20.0 - 0.1)
    assert lp > l0 > lm                                    # deeper water -> longer wavelength
    assert abs(lp / l0 - 1) < 0.01                         # and a 0.235 m tide is a sub-percent effect at 20 m
    assert abs(lp / l0 - 1) > 1e-4                         # but it is resolved, not quantised to zero
    tmin, tmax, tpk = bs.half_power_band(f, e)
    assert tmin < tpk < tmax
    assert bs.lambda_monochromatic(tpk, 20.0, U=-0.11) < bs.lambda_monochromatic(tpk, 20.0, U=0.0)


# --------------------------------------------------- frozen artifact protection
def test_block39_artifacts_are_untouched():
    """Block40 must not rewrite the frozen Block39 results."""
    b39 = ROOT / "duck_frf/Block39_s1_paper_confirm"
    if not b39.exists():
        pytest.skip("Block39 outputs not in this checkout")
    s = json.loads((b39 / "grd/combined_wr17/combined_summary.json").read_text())
    assert s["n_windows"] == 5000
    assert s["paper_peak_block_bootstrap"]["median"] == pytest.approx(-0.008, abs=0.002)
    r = json.loads((b39 / "grd/far_k4/run.json").read_text())
    assert r["args"]["kmin_factor"] == 4.0 and r["args"]["window"] == 1024.0
    assert r["window_status"]["ok"] == 2218
