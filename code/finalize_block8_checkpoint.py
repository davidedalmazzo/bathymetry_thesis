"""Build the auditable Block-8 ranking and CHECKPOINT_8 report."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / "Block8_validation"
RESULTS = BASE / "results"


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def direction_score(delta):
    if delta is None:
        return 0.0
    if delta <= 5:
        return 1.0
    if delta <= 10:
        return 1.0 - 0.03 * (delta - 5)
    if delta <= 20:
        return 0.85 - 0.03 * (delta - 10)
    if delta <= 30:
        return 0.55 - 0.03 * (delta - 20)
    if delta <= 45:
        return 0.25 * (45 - delta) / 15
    return 0.0


def incidence_score(incidence):
    if incidence is None:
        return 0.0
    if 15 <= incidence <= 35:
        return 1.0
    if 10 <= incidence < 15 or 35 < incidence <= 45:
        return 0.65
    if 5 <= incidence < 10 or 45 < incidence <= 55:
        return 0.35
    return 0.10


def period_score(peak, mean):
    # A true spectral peak is preferred.  A model mean period is allowed only
    # as a lower-confidence screening proxy and is never renamed T_p.
    if peak is not None:
        if peak >= 10: return 1.0
        if peak >= 8: return 0.75
        if peak >= 6: return 0.40
        return 0.10
    if mean is None: return 0.0
    if mean >= 10: return 0.85
    if mean >= 8: return 0.65
    if mean >= 6: return 0.40
    if mean >= 4: return 0.15
    return 0.05


def dwell_score(dwell):
    if dwell is None or dwell < 15 or dwell > 120:
        return 0.0
    return min(1.0, 0.5 + (dwell - 15.0) / 10.0)


def final_score(row):
    verified = row.get("verified_spectrum") is not None
    spec = row.get("verified_spectrum") or {}
    delta = number(spec.get("peak_delta_to_range_axis_deg")) if verified else number(row.get("delta_swell_propagation_to_range_axis_deg"))
    peak = number(spec.get("spectral_peak_period_s")) if verified else None
    mean = number(row.get("swell_wave_mean_period_s"))
    hs = number(spec.get("spectral_hs_m")) if verified else number(row.get("swell_significant_height_m"))
    dominance = number(spec.get("energy_fraction_f_le_0p1_hz")) if verified else number(row.get("swell_to_total_height_ratio"))
    if verified:
        dominance_score = 1.0 if dominance is not None and dominance >= 0.50 else 0.60 if dominance is not None and dominance >= 0.25 else 0.30 if dominance is not None and dominance >= 0.10 else 0.0
    else:
        dominance_score = 0.0 if dominance is None else min(1.0, dominance / 0.80)
    buoy_distance = number(spec.get("buoy_distance_km")) if verified else None
    buoy_score = 1.0 if buoy_distance is not None and buoy_distance <= 20 else 0.85 if buoy_distance is not None and buoy_distance <= 30 else 0.70 if buoy_distance is not None and buoy_distance <= 50 else 0.0
    ocean = number(row.get("ocean_fraction_ne10m")) or 0.0
    ocean_score = min(1.0, max(0.0, (ocean - 0.80) / 0.18))
    components = {
        "direction_25": 25 * direction_score(delta),
        "dwell_15": 15 * dwell_score(number(row.get("catalog_dwell_s"))),
        "period_15": 15 * period_score(peak, mean),
        "wave_height_10": 10 * min(1.0, (hs or 0.0) / 1.5),
        "swell_dominance_10": 10 * dominance_score,
        "incidence_5": 5 * incidence_score(number(row.get("incidence_deg"))),
        "ocean_5": 5 * ocean_score,
        "verified_buoy_15": 15 * buoy_score,
    }
    return sum(components.values()), components


def pros_cons(row, spec):
    dwell, inc = number(row.get("catalog_dwell_s")), number(row.get("incidence_deg"))
    ocean = number(row.get("ocean_fraction_ne10m"))
    model_delta = number(row.get("delta_swell_propagation_to_range_axis_deg"))
    mean = number(row.get("swell_wave_mean_period_s")); swell_h = number(row.get("swell_significant_height_m"))
    ratio = number(row.get("swell_to_total_height_ratio"))
    pros, cons = ["CPHD disponibile"], []
    (pros if dwell is not None and dwell > 20 else cons).append(f"dwell {dwell:.1f} s" if dwell is not None else "dwell assente")
    (pros if inc is not None and 15 <= inc <= 35 else cons).append(f"incidenza {inc:.1f}°" if inc is not None else "incidenza assente")
    (pros if ocean is not None and ocean >= 0.98 else cons).append(f"mare {100*ocean:.1f}%" if ocean is not None else "frazione mare ignota")
    if spec:
        peak, delta, hs = number(spec.get("spectral_peak_period_s")), number(spec.get("peak_delta_to_range_axis_deg")), number(spec.get("spectral_hs_m"))
        pros.append(f"spettro NDBC completo a {number(spec['buoy_distance_km']):.1f} km")
        (pros if delta is not None and delta <= 10 else cons).append(f"picco boa Δrange {delta:.1f}°")
        (pros if peak is not None and peak >= 10 else cons).append(f"Tpicco boa {peak:.2f} s")
        (pros if hs is not None and hs >= 0.75 else cons).append(f"Hs spettrale {hs:.2f} m")
        long_fraction = number(spec.get("energy_fraction_f_le_0p1_hz"))
        (pros if long_fraction is not None and long_fraction >= 0.25 else cons).append(f"energia T≥10 s {100*(long_fraction or 0):.1f}%")
    else:
        cons.append("nessuno spettro di boa verificato entro 50 km")
        (pros if model_delta is not None and model_delta <= 10 else cons).append(f"swell MFWAM Δrange {model_delta:.1f}°" if model_delta is not None else "direzione swell assente")
        (pros if mean is not None and mean >= 10 else cons).append(f"periodo medio swell {mean:.2f} s" if mean is not None else "periodo swell assente")
        (pros if swell_h is not None and swell_h >= 0.75 else cons).append(f"Hs swell MFWAM {swell_h:.2f} m" if swell_h is not None else "Hs swell assente")
        (pros if ratio is not None and ratio >= 0.70 else cons).append(f"Hs swell/total {ratio:.2f}" if ratio is not None else "dominanza swell ignota")
        cons.append("swell_wave_peak_period non disponibile: periodo MFWAM è medio")
    if dwell is not None and dwell > 120:
        cons.append("durata STAC anomala >120 s: esclusa dal ranking scientifico")
    return "; ".join(pros), "; ".join(cons)


def main():
    catalog = {r["collect_name"]: r for r in read_csv(BASE / "umbra_all.csv")}
    waves = read_csv(RESULTS / "wave_model_screen.csv")
    nearest = {r["collect_name"]: r for r in read_csv(RESULTS / "nearest_ndbc_stations.csv")}
    verified = {r["collect_name"]: r for r in read_csv(RESULTS / "verified_ndbc_spectra.csv")}
    ranked = []
    for source in waves:
        row = dict(source); row["verified_spectrum"] = verified.get(row["collect_name"])
        score, components = final_score(row)
        spec = row["verified_spectrum"] or {}
        cat = catalog.get(row["collect_name"], {})
        near = nearest.get(row["collect_name"], {})
        pros, cons = pros_cons(row, spec)
        peak_period = number(spec.get("spectral_peak_period_s"))
        peak_prop = number(spec.get("peak_propagation_to_deg"))
        peak_delta = number(spec.get("peak_delta_to_range_axis_deg"))
        buoy_station = spec.get("station", "")
        buoy_distance = number(spec.get("buoy_distance_km"))
        if spec:
            buoy_data = "NDBC directional spectrum: density, alpha1, alpha2, r1, r2; exact-time subset verified"
            buoy_source = spec.get("source_url", "")
        else:
            buoy_station = near.get("nearest_ndbc_station", "")
            buoy_distance = number(near.get("nearest_ndbc_distance_km"))
            buoy_data = "No verified directional spectrum within 50 km at acquisition"
            buoy_source = near.get("ndbc_swden_thredds_catalog", "")
        compact = {
            "screen_band": row["screen_band"], "collect": row["collect_name"], "catalog_location": cat.get("catalog_location", ""),
            "datetime_utc": row["datetime_utc"], "latitude_deg": row["centroid_lat_deg"], "longitude_deg": row["centroid_lon_deg"],
            "dwell_s": row["catalog_dwell_s"], "incidence_deg": row["incidence_deg"], "range_azimuth_deg": row["range_view_azimuth_deg"],
            "range_axis_deg_mod180": row["range_axis_deg_mod180"], "ocean_fraction": row["ocean_fraction_ne10m"],
            "mfwam_swell_direction_from_deg": row["swell_direction_from_deg"], "mfwam_swell_propagation_to_deg": row["swell_propagation_to_deg"],
            "mfwam_delta_range_axis_deg": row["delta_swell_propagation_to_range_axis_deg"],
            "mfwam_total_hs_m": row["total_significant_wave_height_m"], "mfwam_swell_hs_m": row["swell_significant_height_m"],
            "mfwam_swell_mean_period_s": row["swell_wave_mean_period_s"], "mfwam_swell_peak_period_s": row["swell_wave_peak_period_s"],
            "mfwam_swell_to_total_height_ratio": row["swell_to_total_height_ratio"],
            "verified_buoy_station": buoy_station, "buoy_distance_km": buoy_distance, "buoy_data_availability": buoy_data,
            "buoy_spectral_peak_period_s": peak_period, "buoy_peak_propagation_to_deg": peak_prop, "buoy_peak_delta_range_axis_deg": peak_delta,
            "buoy_spectral_hs_m": number(spec.get("spectral_hs_m")), "buoy_long_energy_fraction_f_le_0p1": number(spec.get("energy_fraction_f_le_0p1_hz")),
            "cphd_size_bytes": row["cphd_size_bytes"], "cphd_size_gb": (number(row["cphd_size_bytes"]) or 0)/1e9,
            "sicd_size_bytes": row["sicd_size_bytes"], "sicd_size_gb": (number(row["sicd_size_bytes"]) or 0)/1e9,
            "physics_validation_score_0_100": score, "score_components_json": json.dumps(components, separators=(",", ":")),
            "pros": pros, "cons": cons, "stac_source_url": row["stac_public_url"], "wave_model_source_url": row["wave_model_query_url"],
            "buoy_source_url": buoy_source,
        }
        ranked.append(compact)
    ranked.sort(key=lambda r: (r["screen_band"] != "long_dwell", -r["physics_validation_score_0_100"], r["collect"]))
    for i, row in enumerate([r for r in ranked if r["screen_band"] == "long_dwell"], 1): row["rank_within_band"] = i
    for i, row in enumerate([r for r in ranked if r["screen_band"] == "short_5_7s"], 1): row["rank_within_band"] = i

    all_path = RESULTS / "ranked_candidates_all.csv"
    fields = list(ranked[0])
    with all_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(ranked)

    long_top = [r for r in ranked if r["screen_band"] == "long_dwell" and number(r["dwell_s"]) <= 120][:15]
    c_collect = "2023-07-13-15-18-26_UMBRA-04"
    c_row = next(r for r in ranked if r["collect"] == c_collect)
    top = long_top + [c_row]
    top[0]["decision_label"] = "A_best_available_conditional"
    # The physically long-swell alternative is explicit even if its aggregate score is not second.
    b_collect = "2025-04-26-14-43-09_UMBRA-08"
    for row in top:
        if row["collect"] == b_collect: row["decision_label"] = "B_long_swell_alternative"
        elif row["collect"] == c_collect: row["decision_label"] = "C_short_dwell_control"
        else: row.setdefault("decision_label", "")
    top_path = RESULTS / "top16_candidates.csv"
    top_fields = list(top[0])
    with top_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=top_fields); writer.writeheader(); writer.writerows(top)

    a = top[0]; b = next(r for r in top if r["collect"] == b_collect); c = c_row
    report = f"""# CHECKPOINT_8 — Umbra validation-scene screening

Generated: {datetime.now(timezone.utc).isoformat()}

## Scope and integrity

- Vandenberg was not processed or modified; it is excluded from ranking.
- Complete public catalog: 12,539/12,539 STAC v2 sidecars; 9,577 with CPHD.
- No CPHD or SICD payload was downloaded. Only catalog JSON, wave-model fields, buoy metadata, and six exact-time buoy spectral subsets were retrieved.
- Marine gate: 51 long-dwell scenes and 60 short controls have at least 80% ocean footprint by Natural Earth 1:10m intersection.

## Direction and period conventions

- Umbra `view:azimuth` is used as the range/view axis and treated as an undirected axis modulo 180°.
- MFWAM and NDBC directions are reported **from**; propagation is `(from + 180°) mod 360°` before computing axial delta.
- MFWAM `swell_wave_period` is a mean period. Its `swell_wave_peak_period` field was null for all 111 screened scenes, so no model mean is relabelled as T_p.
- True peak periods below come only from measured NDBC spectral density.

## Decision

### A — best available, conditional: `{a['collect']}`

- Position/date: {float(a['latitude_deg']):.5f}°, {float(a['longitude_deg']):.5f}°; {a['datetime_utc']}.
- Dwell {float(a['dwell_s']):.1f} s; incidence {float(a['incidence_deg']):.1f}°; ocean fraction {100*float(a['ocean_fraction']):.1f}%.
- NDBC 42084 at {float(a['buoy_distance_km']):.1f} km supplies density + α1 + α2 + r1 + r2 within {abs(float(verified[a['collect']]['buoy_minus_scene_s'])):.0f} s.
- Measured dominant peak: T_p={float(a['buoy_spectral_peak_period_s']):.3f} s, Hs={float(a['buoy_spectral_hs_m']):.3f} m, propagation {float(a['buoy_peak_propagation_to_deg']):.1f}°, Δrange={float(a['buoy_peak_delta_range_axis_deg']):.2f}°.
- Gate: excellent geometry and independent spectrum, but **not a swell-period validation scene**: measured energy at f≤0.1 Hz is {100*float(a['buoy_long_energy_fraction_f_le_0p1']):.2f}% and the dominant peak is short-period wind sea. Keep only as a conditional phase→period test if a 4.26 s component is acceptable.

### B — long-swell alternative, not validation-ready: `{b['collect']}`

- Position/date: {float(b['latitude_deg']):.5f}°, {float(b['longitude_deg']):.5f}°; {b['datetime_utc']}.
- Dwell {float(b['dwell_s']):.1f} s; incidence {float(b['incidence_deg']):.1f}°; ocean fraction {100*float(b['ocean_fraction']):.1f}%.
- MFWAM: total Hs={float(b['mfwam_total_hs_m']):.2f} m, swell Hs={float(b['mfwam_swell_hs_m']):.2f} m, mean swell period={float(b['mfwam_swell_mean_period_s']):.2f} s.
- Gate: strong, long, swell-dominant sea, but Δrange={float(b['mfwam_delta_range_axis_deg']):.2f}° and no verified directional buoy within 50 km. It cannot presently provide independent phase→T_p validation.

### C — 5–7 s control retained: `{c['collect']}`

- Dwell {float(c['dwell_s']):.1f} s; incidence {float(c['incidence_deg']):.1f}°; NDBC 44087 at {float(c['buoy_distance_km']):.1f} km.
- Measured T_p={float(c['buoy_spectral_peak_period_s']):.3f} s and Δrange={float(c['buoy_peak_delta_range_axis_deg']):.2f}°, with complete directional coefficients.
- Gate: useful TerraSAR-X/CSG-like timing control, but Hs={float(c['buoy_spectral_hs_m']):.3f} m is low and incidence {float(c['incidence_deg']):.1f}° is outside the preferred interval; retain as a weak-signal control, not the primary validation scene.

## Overall conclusion

The complete catalog contains **no scene that satisfies all ideal gates simultaneously**: long dwell, preferred incidence, strong narrow swell with T_p≥10 s, propagation within 10° of range, and a verified directional spectrum within 50 km. Candidate A is the best independently observed phase-period case but has T_p≈4.26 s; B has the desired long swell but lacks geometry/ground truth; C is a low-energy short-dwell control. Therefore no download >1 GB is authorized at CHECKPOINT_8.

## Artifacts

- `top16_candidates.csv`: requested 10–20 candidate table (15 long-dwell + one short control).
- `ranked_candidates_all.csv`: all 111 marine candidates and score decomposition.
- `verified_ndbc_spectra.csv`: six exact-time spectra and directional diagnostics.

## Sources

- Umbra open data: https://registry.opendata.aws/umbra-open-data/
- Umbra metadata fields: https://docs.canopy.umbra.space/docs/collect-metadata
- Open-Meteo marine fields/conventions: https://open-meteo.com/en/docs/marine-weather-api
- Natural Earth land: https://www.naturalearthdata.com/downloads/10m-physical-vectors/10m-land/
- NDBC spectral conventions: https://www.ndbc.noaa.gov/faq/measdes.shtml
- NDBC historical spectral data: https://www.ndbc.noaa.gov/data/historical/
- CDIP THREDDS data access: https://cdip.ucsd.edu/m/documents/data_access.html
"""
    checkpoint = RESULTS / "CHECKPOINT_8.md"
    checkpoint.write_text(report, encoding="utf-8")
    manifest = {"generated_utc": datetime.now(timezone.utc).isoformat(), "top_rows": len(top), "all_ranked_rows": len(ranked),
                "decision_A": a["collect"], "decision_B": b["collect"], "decision_C": c["collect"],
                "hard_conclusion": "No scene meets all ideal validation gates; no >1 GB download authorized.",
                "top_csv_sha256": hashlib.sha256(top_path.read_bytes()).hexdigest(), "all_csv_sha256": hashlib.sha256(all_path.read_bytes()).hexdigest(),
                "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest()}
    (RESULTS / "CHECKPOINT_8_MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
