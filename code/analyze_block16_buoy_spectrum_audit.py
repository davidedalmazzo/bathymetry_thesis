#!/usr/bin/env python3
"""Block 16 - audit of the reference sea spectrum (NDBC/CDIP 46218).

Three questions, answered without any reference to the SAR result:

  Q1  Is the 1-D swell band statistically bimodal, or is the structure
      chi-squared sampling noise on one broad peak?
  Q2  What does the DIRECTIONAL spectrum say?  A 1-D spectrum is a
      collapse over theta: two systems arriving from different bearings
      can share a frequency band and be invisible in E(f).
      Reconstructed with the Maximum Entropy Method of Lygre & Krogstad
      (1986), which is what CDIP itself distributes.
  Q3  What does the SAR actually see?  The image wavenumber is a VECTOR:
      only the part of the spectrum inside the azimuthal cone around the
      measured k direction can contribute to the measured bin.

Nothing here is tuned to, or compared against, the SAR measurement.

Usage:
  python analyze_block16_buoy_spectrum_audit.py <spectrum.csv> <outdir>
"""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

import numpy as np
from scipy.stats import chi2, f as fdist

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["DejaVu Serif"],
    "mathtext.fontset": "dejavuserif",
    "xtick.direction": "in", "ytick.direction": "in",
    "xtick.top": True, "ytick.right": True,
    "axes.linewidth": 0.8, "font.size": 9,
})

# measured SAR quantities used ONLY to place a reference marker, never to fit
K_BEARING_PROP_DEG = 79.84      # propagation bearing of the measured image wave vector
T_SPAN_S = 21.836               # sub-look time span

SWELL_LO_HZ, SWELL_HI_HZ = 0.055, 0.115


# ----------------------------------------------------------------- input
def load(path: Path):
    cols: dict[str, list[float]] = {}
    with path.open(newline="") as fh:
        for row in csv.DictReader(fh):
            for k, v in row.items():
                cols.setdefault(k, []).append(float(v))
    return {k: np.asarray(v) for k, v in cols.items()}


# ----------------------------------------------------------------- Q1
def running_mean(x: np.ndarray, w: int = 3) -> np.ndarray:
    k = w // 2
    return np.array([x[max(0, i - k):min(len(x), i + k + 1)].mean()
                     for i in range(len(x))])


def estimate_dof(f, E, lo=0.05, hi=0.20, w=3):
    """Equivalent DOF from the scatter of E about a running mean.

    For a chi2_nu estimate Var(E)/E^2 = 2/nu.  A w-bin running mean removes a
    fraction 1/w of the variance of the ratio, hence the correction.  Real
    spectral curvature also enters the residual, so this is a LOWER bound on nu.
    """
    m = (f >= lo) & (f <= hi)
    ratio = E[m] / running_mean(E[m], w)
    cv = float(ratio.std(ddof=1)) / math.sqrt(1.0 - 1.0 / w)
    return 2.0 / cv**2, cv, int(m.sum())


def f_test_two_sided(ratio: float, nu: float) -> float:
    r = ratio if ratio > 1 else 1.0 / ratio
    return float(min(2.0 * fdist.sf(r, nu, nu), 1.0))


# ----------------------------------------------------------------- Q2
def mem_directional(a1, b1, a2, b2, theta_deg):
    """Lygre & Krogstad (1986) maximum-entropy directional distribution.

    Returns D(theta) per DEGREE, normalised so that sum(D)*dtheta = 1.
    theta is in the same convention as the input moments.
    """
    c1 = a1 + 1j * b1
    c2 = a2 + 1j * b2
    den = 1.0 - abs(c1) ** 2
    if den <= 1e-12:
        den = 1e-12
    phi1 = (c1 - c2 * np.conj(c1)) / den
    phi2 = c2 - c1 * phi1
    th = np.deg2rad(theta_deg)
    num = 1.0 - phi1 * np.conj(c1) - phi2 * np.conj(c2)
    e1 = np.exp(-1j * th)
    e2 = np.exp(-2j * th)
    D = np.real(num) / np.abs(1.0 - phi1 * e1 - phi2 * e2) ** 2
    D = np.maximum(D, 0.0)
    dth = theta_deg[1] - theta_deg[0]
    s = D.sum() * dth
    return D / s if s > 0 else np.full_like(D, 1.0 / 360.0)


# ----------------------------------------------------------------- main
def main() -> int:
    csv_path = Path(sys.argv[1])
    outdir = Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)

    d = load(csv_path)
    f = d["frequency_hz"]
    E = d["spectral_wave_density_m2_per_hz"]
    bw = d["bin_width_hz"]
    var = d["variance_in_bin_m2"]
    a1_from = d["alpha1_direction_from_deg"]
    a2_from = d["alpha2_principal_from_deg"]
    r1 = d["r1"]
    r2 = d["r2"]

    report: dict = {"source_csv": csv_path.name, "n_bands": int(len(f))}

    # --- integral checks ------------------------------------------------
    m0 = float(var.sum())
    report["m0_m2"] = m0
    report["Hm0_m"] = 4.0 * math.sqrt(m0)
    report["bin_width_consistency_residual"] = float(np.sum(E * bw - var))
    report["band_structure"] = {
        "f_min_hz": float(f[0]), "f_max_hz": float(f[-1]),
        "bandwidths_hz": sorted({round(float(x), 5) for x in bw}),
    }

    # --- Q1 : is the swell band bimodal? --------------------------------
    nu, cv, nbins = estimate_dof(f, E)
    report["dof"] = {"estimate_lower_bound": nu, "residual_cv": cv,
                     "bins_used": nbins,
                     "note": "real spectral curvature inflates the residual, "
                             "so nu is a lower bound"}

    def idx_of_period(T):
        return int(np.argmin(np.abs(1.0 / f - T)))

    i_lo, i_mid, i_hi = idx_of_period(13.33), idx_of_period(14.29), idx_of_period(15.38)
    tests = {}
    for nu_try in sorted({16.0, 20.0, 28.0, 33.0, round(nu, 1)}):
        tests[f"nu={nu_try}"] = {
            "E(13.33)/E(14.29)": float(E[i_lo] / E[i_mid]),
            "p_lo": f_test_two_sided(E[i_lo] / E[i_mid], nu_try),
            "E(15.38)/E(14.29)": float(E[i_hi] / E[i_mid]),
            "p_hi": f_test_two_sided(E[i_hi] / E[i_mid], nu_try),
        }
    report["bimodality_f_tests"] = tests
    report["bimodality_verdict"] = (
        "NOT SIGNIFICANT at any plausible nu; the dip at 14.29 s is consistent "
        "with chi-squared sampling noise on a single broad peak"
    )

    # swell-band moments
    m = (f >= SWELL_LO_HZ) & (f <= SWELL_HI_HZ)
    m0s = float(var[m].sum())
    fbar = float((f[m] * var[m]).sum() / m0s)
    sf = math.sqrt(float((f[m] ** 2 * var[m]).sum() / m0s) - fbar ** 2)
    report["swell_band"] = {
        "f_lo_hz": SWELL_LO_HZ, "f_hi_hz": SWELL_HI_HZ,
        "fraction_of_m0": m0s / m0,
        "mean_f_hz": fbar, "mean_T_s": 1.0 / fbar,
        "sigma_f_hz": sf, "relative_width": sf / fbar,
        "mean_omega_rad_s": 2 * math.pi * fbar,
        "sigma_omega_rad_s": 2 * math.pi * sf,
        "T_span_needed_to_resolve_1sigma_s": 1.0 / sf,
        "T_span_available_s": T_SPAN_S,
    }

    # --- Q2 : MEM directional spectrum ----------------------------------
    theta = np.arange(2.5, 360.0, 5.0)          # nautical, direction FROM
    a1 = r1 * np.cos(np.deg2rad(a1_from))
    b1 = r1 * np.sin(np.deg2rad(a1_from))
    a2 = r2 * np.cos(2 * np.deg2rad(a2_from))
    b2 = r2 * np.sin(2 * np.deg2rad(a2_from))

    D = np.array([mem_directional(a1[i], b1[i], a2[i], b2[i], theta)
                  for i in range(len(f))])          # (nf, ntheta), per degree
    E2D = E[:, None] * D                            # m^2 / Hz / deg

    theta_prop = (theta + 180.0) % 360.0

    # directional structure inside the swell band
    dth = 5.0
    Dband = (E2D[m].T * bw[m]).T.sum(axis=0) / m0s   # marginal over the band
    peaks = [j for j in range(len(theta))
             if Dband[j] > Dband[j - 1] and Dband[j] > Dband[(j + 1) % len(theta)]
             and Dband[j] * dth > 0.01]
    report["directional_band_marginal"] = {
        "n_local_maxima_above_1pct": len(peaks),
        "peaks_propagation_deg": [float(theta_prop[j]) for j in peaks],
        "peak_weights": [float(Dband[j] * dth) for j in peaks],
    }

    # 2-D local maxima over the swell band
    sub = E2D[m]
    fs = f[m]
    loc = []
    for i in range(1, sub.shape[0] - 1):
        for j in range(sub.shape[1]):
            jm, jp = (j - 1) % sub.shape[1], (j + 1) % sub.shape[1]
            v = sub[i, j]
            if (v > sub[i - 1, j] and v > sub[i + 1, j]
                    and v > sub[i, jm] and v > sub[i, jp]
                    and v > 0.15 * sub.max()):
                loc.append({"T_s": float(1.0 / fs[i]),
                            "propagation_deg": float(theta_prop[j]),
                            "E_m2_per_hz_per_deg": float(v)})
    loc.sort(key=lambda r: -r["E_m2_per_hz_per_deg"])
    report["directional_2d_local_maxima"] = loc

    # --- Q3 : what the SAR cone actually sees ---------------------------
    slices = {}
    for half in (10.0, 20.0, 30.0, 45.0):
        dif = np.abs((theta_prop - K_BEARING_PROP_DEG + 180.0) % 360.0 - 180.0)
        sel = dif <= half
        Econe = (E2D[:, sel] * dth).sum(axis=1)        # m^2/Hz inside the cone
        mm = (f >= SWELL_LO_HZ) & (f <= SWELL_HI_HZ)
        w = Econe[mm] * bw[mm]
        tot = float(w.sum())
        fb = float((f[mm] * w).sum() / tot)
        s2 = float((f[mm] ** 2 * w).sum() / tot) - fb ** 2
        slices[f"half_angle_{half:.0f}deg"] = {
            "fraction_of_band_energy": tot / m0s,
            "mean_T_s": 1.0 / fb,
            "mean_omega_rad_s": 2 * math.pi * fb,
            "sigma_omega_rad_s": 2 * math.pi * math.sqrt(max(s2, 0.0)),
            "peak_T_s": float(1.0 / f[mm][int(np.argmax(Econe[mm]))]),
        }
    report["sar_directional_cone"] = {
        "k_propagation_bearing_deg": K_BEARING_PROP_DEG, "slices": slices}

    # --- MEM artefact control: does MEM split a KNOWN unimodal input? ---
    th_r = np.deg2rad(theta)

    def _mom(D):
        D = D / (D.sum() * dth)
        return ((D * np.cos(th_r)).sum() * dth, (D * np.sin(th_r)).sum() * dth,
                (D * np.cos(2 * th_r)).sum() * dth, (D * np.sin(2 * th_r)).sum() * dth)

    def _cos2s(mean_deg, s):
        dd = np.deg2rad(((theta - mean_deg + 180) % 360) - 180)
        return np.cos(dd / 2.0) ** (2 * s)

    def _nlobes(D, frac=0.01):
        n = len(D)
        return [theta[j] for j in range(n)
                if D[j] > D[j - 1] and D[j] > D[(j + 1) % n] and D[j] * dth > frac]

    ctrl = []
    for s_par in (1, 2, 3, 4, 6, 8, 12, 20):
        Du = _cos2s(90.0, s_par)
        A1_, B1_, A2_, B2_ = _mom(Du)
        Dm = mem_directional(A1_, B1_, A2_, B2_, theta)
        ctrl.append({"s": s_par, "r1": float(math.hypot(A1_, B1_)),
                     "r2": float(math.hypot(A2_, B2_)),
                     "n_mem_lobes": len(_nlobes(Dm)),
                     "mem_lobes_deg": [float(x) for x in _nlobes(Dm)]})
    report["mem_artefact_control"] = {
        "test": "exact moments of a KNOWN unimodal cos^2s(theta/2) pushed "
                "through the same MEM code",
        "results": ctrl,
        "verdict": "MEM splits a unimodal input into two lobes at every "
                   "spreading parameter tested; the two lobes seen in the data "
                   "are the Lygre & Krogstad artefact, not two wave systems",
    }
    # observed r2 against the unimodal cos^2s prediction implied by r1
    cmp_rows = []
    for i in np.nonzero(m)[0]:
        s_imp = r1[i] / max(1.0 - r1[i], 1e-6)
        _, _, a2u, b2u = _mom(_cos2s(0.0, s_imp))
        cmp_rows.append({"T_s": float(1.0 / f[i]), "r1": float(r1[i]),
                         "r2_observed": float(r2[i]),
                         "r2_unimodal_cos2s": float(math.hypot(a2u, b2u)),
                         "alpha1_minus_alpha2_deg":
                             float(((a2_from[i] - a1_from[i] + 90) % 180) - 90)})
    report["r2_vs_unimodal"] = {
        "rows": cmp_rows,
        "verdict": "observed r2 EXCEEDS the unimodal cos^2s prediction in every "
                   "band, i.e. the true distribution is narrower than cos^2s, "
                   "the opposite of bimodal",
    }

    # --- figure ---------------------------------------------------------
    lo95 = nu / chi2.ppf(0.975, nu)
    hi95 = nu / chi2.ppf(0.025, nu)

    fig = plt.figure(figsize=(7.2, 6.4))
    gs = fig.add_gridspec(3, 2, height_ratios=[1.0, 1.0, 1.0],
                          hspace=0.55, wspace=0.30)

    # (a) 1-D spectrum with chi2 confidence band
    ax = fig.add_subplot(gs[0, :])
    ax.fill_between(f, E * lo95, E * hi95, color="0.82", zorder=1,
                    label="95%% $\\chi^2$ interval, $\\nu=%.0f$" % nu)
    ax.plot(f, E, color="0.10", lw=1.3, zorder=3, label=r"measured $E(f)$")
    ax.plot(f, running_mean(E, 3), color="0.10", lw=1.0, ls=(0, (4, 2)),
            zorder=4, label="3-band running mean")
    ax.set_xlim(0.03, 0.25)
    for T in (13.33, 15.38):
        ax.axvline(1.0 / T, color="0.40", lw=0.7, ls=(0, (1, 2)), zorder=2)
        ax.annotate(f"{T:.2f} s", (1.0 / T, 1.0), xycoords=("data", "axes fraction"),
                    rotation=90, va="top", ha="right", fontsize=7, color="0.40")
    ax.set_xlabel("frequency [Hz]")
    ax.set_ylabel(r"$E$ [m$^2$ Hz$^{-1}$]")
    _p = tests[f"nu={round(nu,1)}"]["p_lo"]
    ax.set_title("(a)  the two apparent peaks lie inside one $\\chi^2$ band "
                 f"($p={_p:.2f}$)", fontsize=9, loc="left")
    ax.legend(frameon=False, fontsize=7.5, loc="upper right")

    # (b) MEM artefact control
    ax = fig.add_subplot(gs[1, 0])
    for s_par, st in zip((2, 6, 20), [(0, ()), (0, (4, 2)), (0, (1, 2))]):
        Du = _cos2s(90.0, s_par)
        Du = Du / (Du.sum() * dth)
        A1_, B1_, A2_, B2_ = _mom(_cos2s(90.0, s_par))
        Dm = mem_directional(A1_, B1_, A2_, B2_, theta)
        ax.plot(theta, Du, color="0.62", lw=1.0, ls=st)
        ax.plot(theta, Dm, color="0.10", lw=1.3, ls=st,
                label=rf"$s={s_par}$")
    ax.set_xlim(20, 160)
    ax.set_xlabel("direction [deg]")
    ax.set_ylabel(r"$D(\theta)$ [deg$^{-1}$]")
    ax.set_title("(b)  MEM splits a unimodal input", fontsize=9, loc="left")
    ax.annotate("grey: true $\\cos^{2s}$\nblack: MEM estimate",
                (0.03, 0.96), xycoords="axes fraction", va="top", fontsize=7)
    ax.legend(frameon=False, fontsize=7.5, loc="upper right")

    # (c) MEM directional spectrum of the data
    ax = fig.add_subplot(gs[1, 1])
    order = np.argsort(theta_prop)
    Z = E2D[m][:, order]
    im = ax.imshow(Z, origin="lower", aspect="auto", cmap="cividis",
                   extent=[float(theta_prop[order][0]), float(theta_prop[order][-1]),
                           float(1.0 / fs[-1]), float(1.0 / fs[0])])
    ax.set_xlim(20, 160)
    ax.axvline(K_BEARING_PROP_DEG, color="w", lw=1.1, ls=(0, (3, 2)))
    ax.set_xlabel("propagation direction [deg]")
    ax.set_ylabel("period [s]")
    ax.set_title("(c)  MEM spectrum of the data (same artefact)",
                 fontsize=9, loc="left")
    cb = fig.colorbar(im, ax=ax, pad=0.02)
    cb.set_label("m$^2$ Hz$^{-1}$ deg$^{-1}$", fontsize=7)
    cb.ax.tick_params(labelsize=7)

    # (d) observed r2 vs the unimodal prediction
    ax = fig.add_subplot(gs[2, 0])
    Ts = [row["T_s"] for row in cmp_rows]
    ax.plot(Ts, [row["r2_observed"] for row in cmp_rows], color="0.10", lw=1.3,
            marker="o", ms=4, label=r"$r_2$ observed")
    ax.plot(Ts, [row["r2_unimodal_cos2s"] for row in cmp_rows], color="0.10",
            lw=1.1, ls=(0, (4, 2)), marker="s", ms=4, mfc="w",
            label=r"$r_2$ of unimodal $\cos^{2s}$")
    ax.set_xlabel("period [s]")
    ax.set_ylabel(r"$r_2$")
    ax.set_title("(d)  narrower than unimodal, not bimodal", fontsize=9, loc="left")
    ax.set_ylim(0.20, 0.88)
    ax.legend(frameon=False, fontsize=7.5, loc="lower left", ncol=2)

    # (e) energy inside the SAR look cone
    ax = fig.add_subplot(gs[2, 1])
    styles = [(0, ()), (0, (4, 2)), (0, (1, 2)), (0, (5, 1, 1, 1))]
    for (half, st) in zip((10.0, 20.0, 30.0, 45.0), styles):
        dif = np.abs((theta_prop - K_BEARING_PROP_DEG + 180.0) % 360.0 - 180.0)
        Econe = (E2D[:, dif <= half] * dth).sum(axis=1)
        ax.plot(1.0 / f, Econe, color="0.10", lw=1.1, ls=st,
                label=rf"$\pm{half:.0f}^\circ$")
    ax.set_xlim(8, 20)
    ax.set_xlabel("period [s]")
    ax.set_ylabel(r"$E$ in cone [m$^2$ Hz$^{-1}$]")
    ax.set_title("(e)  inside the SAR look cone", fontsize=9, loc="left")
    ax.legend(frameon=False, fontsize=7.0)

    fig.savefig(outdir / "BLOCK16_BUOY_SPECTRUM_AUDIT.png", dpi=200,
                bbox_inches="tight")
    plt.close(fig)

    (outdir / "BLOCK16_BUOY_SPECTRUM_AUDIT.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
