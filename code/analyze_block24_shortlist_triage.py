#!/usr/bin/env python3
"""Block 24 — triage offline della shortlist Block21 per l'obiettivo FREQUENZA.

Completa il Block23 (candidato 2) e prosegue su 3, 4, 5 come richiesto, ma lo
fa in un colpo solo e **senza rete**: ogni grandezza qui viene da artefatti
gia' congelati (Block16A marine geometry, Block21 shortlist e reference bins).

Quattro discriminanti, nessuno dei quali e' un gate del Block21:

  D1  disponibilita' PUBBLICA del prodotto complesso
      `sicd_size_bytes` / `cphd_size_bytes` non nulli nella shortlist. Il
      Block23 ha dimostrato che una dichiarazione STAC non implica un oggetto
      pubblico: il candidato 2 e' l'unico con entrambe le dimensioni nulle ed
      e' l'unico che ha dato 404 su ogni nome. La dimensione nulla e' quindi
      il segnale offline della non disponibilita'.

  D2  allineamento onda-range
      asse range locale = (view_azimuth - 180) mod 360; differenza assiale
      modulo 180 contro la direzione di propagazione della stessa banda.
      Convenzione verificata: riproduce 67.17 deg del Block22 (cand. 1) e
      71.82 deg del Block23 (cand. 2).

  D3  risoluzione spettrale del numero d'onda
      dL/L = L / W_ROI. E' il limite che ha prodotto il taglio a L>200 m di
      Romeiser: con 3-5 lunghezze d'onda nella finestra il picco non si
      localizza meglio del 20-35%.

  D4  rotazione di fase nella base temporale utile
      d_phi = omega * 0.65 * dwell. Deve stare fra ~45 e ~300 gradi.

  D5  ENERGIA DELLO STATO DI MARE — il gate mancante.
      Hm0 ricalcolato dai bin del riferimento. Il Block21 usa
      `joint_energy_coverage`, che misura la COMPLETEZZA del record della boa,
      non l'energia del mare.

Nessun dato SAR letto, nessuna rete, nessuna raccomandazione di download.
"""
from __future__ import annotations
import csv, json, math, sys
from pathlib import Path

G = 9.80665
F_BASE = 0.65
BETA_REF = 79.75          # R/V misurato a Vandenberg, usato solo come scala


def axial_difference_deg(a: float, b: float) -> float:
    """Differenza fra due assi non orientati, modulo 180."""
    return abs(((a - b + 90.0) % 180.0) - 90.0)


def local_range_axis_deg(view_azimuth_deg: float) -> float:
    return (view_azimuth_deg - 180.0) % 360.0


def deep_wavelength(T: float) -> float:
    return G * T * T / (2.0 * math.pi)


def phase_rotation_deg(T: float, dwell_s: float, f_base: float = F_BASE) -> float:
    return math.degrees((2.0 * math.pi / T) * f_base * dwell_s)


def cutoff_estimate_m(Hm0: float, T: float, beta: float, incidence_deg: float) -> float:
    sigma_u = (Hm0 / 4.0) * (2.0 * math.pi / T)
    return 2.0 * math.pi * beta * sigma_u * math.sin(math.radians(incidence_deg))


def moments_from_bins(bins) -> dict:
    m0 = 0.0; peak_e = -1.0; peak_f = None
    for b in bins:
        try:
            f = float(b["frequency_hz"]); e = float(b["spectral_wave_density"])
            w = float(b["band_width_hz"])
        except (TypeError, ValueError):
            continue
        m0 += e * w
        if e > peak_e:
            peak_e, peak_f = e, f
    return {"m0_m2": m0, "Hm0_m": 4.0 * math.sqrt(m0) if m0 > 0 else float("nan"),
            "Tp_s": (1.0 / peak_f) if peak_f else float("nan")}


def evaluate(row, geom, bins, dwell_s):
    T = float(row["peak_period_s"])
    prop = float(row["propagation_to_deg"])
    W = float(row["roi_square_size_m"])
    inc = float(geom["incidence_deg"]); va = float(geom["view_azimuth_deg"])
    rax = local_range_axis_deg(va)
    d_ax = axial_difference_deg(rax, prop)
    L = deep_wavelength(T)
    mom = moments_from_bins(bins)
    lam_c = cutoff_estimate_m(mom["Hm0_m"], T, BETA_REF, inc)
    sin_phi = math.sin(math.radians(d_ax))
    lam_apparent = L / sin_phi if sin_phi > 1e-6 else float("inf")

    sicd = row.get("sicd_size_bytes") or ""
    cphd = row.get("cphd_size_bytes") or ""
    public = bool(sicd.strip()) or bool(cphd.strip())

    return {
        "rank": int(row["rank"]), "collect_name": row["collect_name"],
        "collect_id": row["collect_id"],
        "D1_public_complex": public,
        "sicd_bytes": int(sicd) if sicd.strip() else None,
        "cphd_bytes": int(cphd) if cphd.strip() else None,
        "D2_axial_difference_deg": d_ax,
        "local_range_axis_deg": rax, "incidence_deg": inc,
        "D3_dL_over_L": L / W, "L_deep_m": L, "roi_m": W,
        "wavelengths_in_roi": W / L,
        "D4_phase_rotation_deg": phase_rotation_deg(T, dwell_s),
        "catalog_duration_s": dwell_s,
        "D5_Hm0_m": mom["Hm0_m"], "m0_m2": mom["m0_m2"],
        "peak_period_s": T, "steepness_H_over_L": mom["Hm0_m"] / L,
        "lambda_cutoff_est_m": lam_c,
        "apparent_azimuth_wavelength_m": lam_apparent,
        "cutoff_ok": lam_apparent >= lam_c,
        "station_id": row["station_id"],
        "station_distance_km": float(row["station_distance_km"]),
        "observation_offset_s": float(row["observation_offset_s"]),
    }


def main() -> int:
    b21 = Path(sys.argv[1]); geom_csv = Path(sys.argv[2])
    csv.field_size_limit(10 ** 9)

    short = list(csv.DictReader(open(b21 / "BLOCK21_SHORTLIST.csv")))
    bins = {}
    for r in csv.DictReader(open(b21 / "BLOCK21_REFERENCE_BINS.csv")):
        bins.setdefault(r["acquisition_key"], []).append(r)

    want = {r["collect_id"]: r for r in short}
    geom = {}
    with open(geom_csv, newline="", encoding="utf-8", errors="replace") as fh:
        for r in csv.DictReader(fh):
            cid = (r.get("collect_id") or "").strip()
            if cid in want:
                geom.setdefault(cid, r)

    out = []
    for r in sorted(short, key=lambda x: int(x["rank"])):
        cid = r["collect_id"]
        if cid not in geom:
            out.append({"rank": int(r["rank"]), "collect_name": r["collect_name"],
                        "error": "no marine-geometry row"}); continue
        out.append(evaluate(r, geom[cid], bins.get(r["acquisition_key"], []),
                            float(r["catalog_duration_s"])))

    hdr = (f"{'#':>2} {'pubbl':>6} {'Δax':>6} {'dL/L':>6} {'λ/ROI':>6} "
           f"{'dphi':>7} {'Hm0':>6} {'T':>6} {'cutoff':>7}")
    print(hdr); print("-" * len(hdr))
    for d in out:
        if "error" in d:
            print(f"{d['rank']:>2}  {d['error']}"); continue
        print(f"{d['rank']:>2} {'si' if d['D1_public_complex'] else 'NO':>6} "
              f"{d['D2_axial_difference_deg']:6.1f} {d['D3_dL_over_L']:6.3f} "
              f"{d['wavelengths_in_roi']:6.1f} {d['D4_phase_rotation_deg']:6.0f}d "
              f"{d['D5_Hm0_m']:6.2f} {d['peak_period_s']:6.2f} "
              f"{'ok' if d['cutoff_ok'] else 'NO':>7}")

    json.dump(out, open("BLOCK24_SHORTLIST_TRIAGE.json", "w"), indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
