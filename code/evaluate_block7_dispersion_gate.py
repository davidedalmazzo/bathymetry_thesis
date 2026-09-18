"""Evaluate whether Block-7 supports an internal omega(k) dispersion fit."""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path


ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'umbra/Vandenberg'/"results"/"analysis_block7";G=9.80665


def main():
    spatial=json.loads((OUT/"BLOCK7_SPATIAL_CONVERGENCE.json").read_text());bathy=json.loads((OUT/"BLOCK7_BATHYMETRY_STATS.json").read_text())
    largest=spatial["summary_nearshore_anchored_by_size"][-1];conv=spatial["large_roi_convergence"];hom=spatial["homogeneity"]
    df=largest["median_native_delta_f_cycles_per_m"];fwhm=largest["median_radial_fwhm_cycles_per_m"];lam=largest["lambda_median_m"]
    spread=(largest["lambda_p10_p90_m"][1]-largest["lambda_p10_p90_m"][0])/lam
    independent=fwhm/df;h=bathy["roi_statistics"][-1]["depth_median_m"];k=2*math.pi/lam;omega=math.sqrt(G*k*math.tanh(k*h));cg=.5*omega/k*(1+2*k*h/math.sinh(2*k*h));delta_omega=cg*2*math.pi*df
    criteria={
        "at_least_10_wavelengths_parallel":{"value":largest["L_parallel_m"]/lam,"threshold":10,"pass":largest["L_parallel_m"]/lam>=10},
        "at_least_4_independent_radial_elements_in_lobe":{"value":independent,"threshold":4,"pass":independent>=4},
        "last_three_peak_medians_relative_range_le_5pct":{"value":conv["last_three_lambda_relative_range"],"threshold":.05,"pass":conv["last_three_lambda_relative_range"]<=.05},
        "largest_roi_look_window_p10_p90_relative_spread_le_15pct":{"value":spread,"threshold":.15,"pass":spread<=.15},
        "cross_shore_subroi_lambda_cv_le_10pct":{"value":hom["cross_shore_lambda_cv"],"threshold":.10,"pass":hom["cross_shore_lambda_cv"]<=.10},
        "alongshore_subroi_lambda_cv_le_10pct":{"value":hom["alongshore_lambda_cv"],"threshold":.10,"pass":hom["alongshore_lambda_cv"]<=.10},
    }
    passed=all(x["pass"] for x in criteria.values())
    result={"generated_utc":datetime.now(timezone.utc).isoformat(),"gate_passed":passed,"criteria":criteria,
        "resolution_diagnostics":{"native_delta_f_parallel_cycles_per_m":df,"native_delta_k_parallel_rad_per_m":2*math.pi*df,"radial_fwhm_cycles_per_m":fwhm,"radial_fwhm_over_native_bin":independent,
            "largest_L_parallel_m":largest["L_parallel_m"],"median_peak_lambda_m":lam,"look_window_p10_p90_lambda_m":largest["lambda_p10_p90_m"]},
        "independent_bathymetry_dispersion_scale":{"depth_median_NAVD88_m":h,"omega_at_peak_rad_per_s":omega,"period_at_peak_s":2*math.pi/omega,"group_velocity_m_per_s":cg,"expected_delta_omega_per_native_radial_bin_rad_per_s":delta_omega},
        "omega_k_test":{"performed":False if not passed else None,"models_fitted":[],"bootstrap_performed":False if not passed else None,
            "reason":"The broadened main lobe spans only about two native radial resolution elements, while look/window and alongshore sub-ROI peak spreads fail robustness thresholds. Fitting b0 and b1 to zero-padded or overlapping patch samples would create pseudo-replication and no defensible bootstrap uncertainty on d omega/dk." if not passed else "Gate passed; enlarged sliding looks required."},
        "dwell_sweep_performed":False,"definitive_bathymetric_inversion_performed":False}
    (OUT/"BLOCK7_INTERNAL_DISPERSION_GATE.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))


if __name__=="__main__":main()
